"""
Celery task: fetch Open-Meteo weather forecasts for all active games
and persist WeatherReading rows.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.ingestion.weather_adapter import fetch_game_weather
from app.db.session import AsyncSessionLocal
from app.db.crud import get_games_for_week, save_weather_reading

logger = logging.getLogger(__name__)
NFL_SEASON = 2026


@celery_app.task(
    name="app.tasks.ingest_weather.run_weather_ingestion",
    bind=True,
    max_retries=3,
)
def run_weather_ingestion(self, season: int = None, week: int = None):
    loop = asyncio.new_event_loop()
    try:
        saved = loop.run_until_complete(
            _fetch_and_persist(season or NFL_SEASON, week or _current_week())
        )
        logger.info("Weather ingestion: %d readings saved", saved)
        return {"status": "ok", "saved": saved}
    except Exception as exc:
        logger.error("Weather ingestion failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
    finally:
        loop.close()


async def _fetch_and_persist(season: int, week: int) -> int:
    saved = 0
    async with AsyncSessionLocal() as db:
        games = await get_games_for_week(db, season, week)
        for game in games:
            if game.status == "final":
                continue
            if not game.home_team:
                continue
            try:
                wx = await fetch_game_weather(
                    game.home_team.abbreviation,
                    game.game_time,
                )
                if wx:
                    await save_weather_reading(db, game.id, game.game_time, wx)
                    saved += 1
            except Exception as exc:
                logger.warning("Weather fetch failed for game_id=%d: %s", game.id, exc)
    return saved


def _current_week() -> int:
    import math
    now = datetime.now(timezone.utc)
    season_start = datetime(now.year, 9, 7, tzinfo=timezone.utc)
    delta = (now - season_start).days
    return max(1, min(22, math.ceil((delta + 1) / 7)))
