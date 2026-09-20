"""
Celery task: ingest NFL odds from ESPN (DraftKings lines via provider 1002)
and persist each game snapshot to the database.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.ingestion.espn_adapter import fetch_espn_scoreboard_odds
from app.db.session import AsyncSessionLocal
from app.db.crud import get_or_create_game, save_odds_snapshot

logger = logging.getLogger(__name__)

# Current season — update each year
NFL_SEASON = 2026


@celery_app.task(
    name="app.tasks.ingest_odds.run_odds_ingestion",
    bind=True,
    max_retries=3,
)
def run_odds_ingestion(self, season: int = None, week: int = None):
    """
    Pull DraftKings lines from ESPN scoreboard and persist OddsSnapshots.
    Season and week default to whatever ESPN's live scoreboard returns.
    """
    loop = asyncio.new_event_loop()
    try:
        games = loop.run_until_complete(
            fetch_espn_scoreboard_odds(season=season or NFL_SEASON, week=week)
        )

        if not games:
            logger.warning("ESPN returned 0 games with odds (season=%s week=%s)", season, week)
            return {"status": "empty", "count": 0}

        saved = loop.run_until_complete(_persist_odds(games, season or NFL_SEASON))
        logger.info("Odds ingestion: %d/%d snapshots saved", saved, len(games))
        return {"status": "ok", "fetched": len(games), "saved": saved}

    except Exception as exc:
        logger.error("ESPN odds ingestion failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


async def _persist_odds(games: list[dict], season: int) -> int:
    """Resolve game rows and write one OddsSnapshot per ESPN event."""
    saved = 0
    async with AsyncSessionLocal() as db:
        for g in games:
            try:
                game_time_raw = g.get("game_time", "")
                game_time = _parse_dt(game_time_raw)
                if not game_time:
                    logger.warning("Unparseable game_time for event %s", g.get("external_id"))
                    continue

                week = _week_from_game_time(game_time)
                game = await get_or_create_game(
                    db,
                    external_id=g["external_id"],
                    home_abbr=g["home_team"],
                    away_abbr=g["away_team"],
                    game_time=game_time,
                    season=season,
                    week=week,
                )
                if not game:
                    continue

                await save_odds_snapshot(db, game.id, g)
                saved += 1

            except Exception as exc:
                logger.warning("Failed persisting snapshot for event %s: %s", g.get("external_id"), exc)

    return saved


def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        # Python 3.11+ fromisoformat handles T17:00Z (no seconds) natively
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)  # naive UTC — DB is TIMESTAMP WITHOUT TIME ZONE
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=None)  # naive UTC — DB is TIMESTAMP WITHOUT TIME ZONE
        except ValueError:
            continue
    return None


def _week_from_game_time(dt: datetime) -> int:
    """
    Approximate NFL week from date. Season opener is the Thursday after
    Labor Day (first Monday of September). Good enough for DB bucketing —
    ESPN's event data has the authoritative week but we use this as fallback.
    """
    # Week 1 starts ~Sept 5–11. Each week = 7 days.
    import math
    season_start = datetime(dt.year, 9, 7)  # naive UTC, matches naive game_time
    delta = (dt - season_start).days
    return max(1, min(22, math.ceil((delta + 1) / 7)))


@celery_app.task(
    name="app.tasks.ingest_odds.run_line_movement_ingestion",
    bind=True,
    max_retries=3,
)
def run_line_movement_ingestion(self, event_id: str, provider_id: str = "1002"):
    """Fetch and store line movement history for one ESPN event."""
    from app.ingestion.espn_adapter import fetch_espn_line_movement
    loop = asyncio.new_event_loop()
    try:
        movements = loop.run_until_complete(
            fetch_espn_line_movement(event_id=event_id, provider_id=provider_id)
        )
        logger.info("Line movement: %d entries for event %s", len(movements), event_id)
        return {"status": "ok", "event_id": event_id, "count": len(movements)}
    except Exception as exc:
        logger.error("Line movement ingestion failed for %s: %s", event_id, exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()


async def _ingest(season: int, week: int) -> dict:
    """Async entry point for direct invocation and testing."""
    games = await fetch_espn_scoreboard_odds(season=season, week=week)
    if not games:
        logger.warning("No games returned for season=%d week=%d", season, week)
        return {"status": "empty", "fetched": 0, "saved": 0}
    saved = await _persist_odds(games, season)
    return {"status": "ok", "fetched": len(games), "saved": saved}
