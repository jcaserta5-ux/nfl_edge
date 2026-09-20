"""
Celery task: ingest ESPN injury designations and persist to the DB.

Schedule: every 3 hours (10800 seconds) — ESPN injury data updates
throughout the week, with the most significant changes on Wed/Thu/Fri
(practice reports).

Strategy:
  1. Fetch all team injuries from ESPN's bulk injuries endpoint
  2. Group by team abbreviation
  3. Resolve team_id from our nfl_teams table
  4. Wipe and replace injury_reports rows for each team (full refresh)
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.ingestion.injury_adapter import fetch_injuries
from app.db.session import AsyncSessionLocal
from app.db.crud import get_all_teams, save_injury_reports

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ingest_injuries.run_injury_ingestion",
    bind=True,
    max_retries=3,
)
def run_injury_ingestion(self):
    loop = asyncio.new_event_loop()
    try:
        total = loop.run_until_complete(_ingest())
        logger.info("Injury ingestion: persisted %d player records", total)
        return {"status": "ok", "total_records": total}
    except Exception as exc:
        logger.error("Injury ingestion failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
    finally:
        loop.close()


async def _ingest() -> int:
    # Fetch all injuries from ESPN
    records = await fetch_injuries()
    if not records:
        logger.warning("Injury fetch returned 0 records — ESPN may be unavailable")
        return 0

    async with AsyncSessionLocal() as db:
        # Build abbreviation → team_id lookup
        teams = await get_all_teams(db)
        abbr_to_id = {t.abbreviation.upper(): t.id for t in teams}

        # Group records by team abbreviation
        by_team: dict[str, list[dict]] = {}
        for rec in records:
            abbr = (rec.get("team_abbreviation") or "").upper()
            if abbr not in by_team:
                by_team[abbr] = []
            by_team[abbr].append(rec)

        total = 0
        for abbr, team_records in by_team.items():
            team_id = abbr_to_id.get(abbr) or abbr_to_id.get(_fallback_abbr(abbr))
            if not team_id:
                logger.debug("No team_id for abbreviation=%s — skipping %d injuries", abbr, len(team_records))
                continue

            count = await save_injury_reports(db, team_id, team_records)
            total += count
            if count:
                logger.debug("Saved %d injuries for %s", count, abbr)

    return total


def _fallback_abbr(abbr: str) -> str:
    mapping = {
        "WSH": "WAS",
        "WAS": "WSH",
        "JAC": "JAX",
        "JAX": "JAC",
        "LVR": "LV",
        "LV": "LVR",
    }
    return mapping.get(abbr, abbr)
