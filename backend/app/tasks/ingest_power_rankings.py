"""
Celery task: ingest ESPN power rankings (FPI) and persist to the DB.

Schedule: daily at 3 AM ET + on-demand.

Strategy:
  1. Try ESPN FPI endpoint (v2 then v1)
  2. Fall back to standings-derived ranking if FPI returns nothing
  3. For each team returned, resolve team_id from our nfl_teams table
     and upsert into power_rankings
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.ingestion.power_rankings_adapter import fetch_power_rankings_v2
from app.db.session import AsyncSessionLocal
from app.db.crud import get_all_teams, upsert_power_ranking

logger = logging.getLogger(__name__)
NFL_SEASON = 2026


@celery_app.task(
    name="app.tasks.ingest_power_rankings.run_power_rankings_ingestion",
    bind=True,
    max_retries=3,
)
def run_power_rankings_ingestion(self, season: int = None, week: int = None):
    loop = asyncio.new_event_loop()
    try:
        s = season or NFL_SEASON
        w = week or _current_week()
        count = loop.run_until_complete(_ingest(s, w))
        logger.info("Power rankings ingestion: upserted %d teams (season=%d week=%d)", count, s, w)
        return {"status": "ok", "upserted": count, "season": s, "week": w}
    except Exception as exc:
        logger.error("Power rankings ingestion failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
    finally:
        loop.close()


async def _ingest(season: int, week: int) -> int:
    # Fetch rankings from ESPN
    rankings = await fetch_power_rankings_v2(season, week)
    if not rankings:
        logger.warning("No power rankings data returned for season=%d week=%d", season, week)
        return 0

    async with AsyncSessionLocal() as db:
        # Build abbreviation → team_id lookup from our DB
        teams = await get_all_teams(db)
        abbr_to_id = {t.abbreviation.upper(): t.id for t in teams}

        upserted = 0
        for rank_data in rankings:
            abbr = (rank_data.get("abbreviation") or "").upper()
            team_id = abbr_to_id.get(abbr)
            if not team_id:
                # Try minor variant remaps
                team_id = abbr_to_id.get(_fallback_abbr(abbr))
            if not team_id:
                logger.debug("No team_id for abbreviation=%s — skipping", abbr)
                continue

            await upsert_power_ranking(db, team_id, season, week, rank_data)
            upserted += 1

    return upserted


def _current_week() -> int:
    import math
    now = datetime.now(timezone.utc)
    season_start = datetime(now.year, 9, 7, tzinfo=timezone.utc)
    delta = (now - season_start).days
    return max(1, min(22, math.ceil((delta + 1) / 7)))


def _fallback_abbr(abbr: str) -> str:
    """Handle edge cases where ESPN and our DB use different abbreviations."""
    mapping = {
        "WSH": "WAS",
        "WAS": "WSH",
        "JAC": "JAX",
        "JAX": "JAC",
        "LVR": "LV",
        "LV": "LVR",
    }
    return mapping.get(abbr, abbr)
