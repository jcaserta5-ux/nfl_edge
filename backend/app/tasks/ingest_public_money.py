"""
Celery task: fetch public betting splits from Action Network and persist
them by merging into the latest OddsSnapshot for each matched game.
"""
import asyncio
import logging
import os

from app.tasks.celery_app import celery_app
from app.ingestion.public_money_adapter import (
    fetch_action_network,
    load_from_file,
    fetch_from_endpoint,
)
from app.ingestion.game_matcher import match_all_an_records
from app.db.session import AsyncSessionLocal
from app.db.crud import merge_public_money_into_snapshot

logger = logging.getLogger(__name__)

NFL_SEASON = 2026


@celery_app.task(
    name="app.tasks.ingest_public_money.run_public_money_ingestion",
    bind=True,
    max_retries=3,
)
def run_public_money_ingestion(self):
    loop = asyncio.new_event_loop()
    try:
        records, source = loop.run_until_complete(_fetch_records())

        if not records:
            logger.warning("No public money records from any source")
            return {"status": "empty", "source": source, "count": 0}

        merged = loop.run_until_complete(_persist_public_money(records))
        logger.info("Public money: %d/%d records merged (source=%s)", merged, len(records), source)
        return {"status": "ok", "source": source, "fetched": len(records), "merged": merged}

    except Exception as exc:
        logger.error("Public money ingestion failed: %s", exc)
        raise self.retry(exc=exc, countdown=90)
    finally:
        loop.close()


async def _fetch_records() -> tuple[list[dict], str]:
    """Try Action Network first, fall back to scraper."""
    # Tier 1 — Action Network
    try:
        records = await fetch_action_network()
        if records:
            return records, "action_network"
        logger.warning("Action Network returned 0 records — falling back to scraper")
    except Exception as exc:
        logger.warning("Action Network failed: %s", exc)

    # Tier 2 — Your scraper
    source = os.getenv("SCRAPER_SOURCE", "file")
    if source == "endpoint":
        url = os.getenv("SCRAPER_ENDPOINT_URL", "")
        key = os.getenv("SCRAPER_API_KEY", "") or None
        if url:
            records = await fetch_from_endpoint(url, key)
            return records, "scraper_endpoint"
    elif source != "disabled":
        path = os.getenv("SCRAPER_FILE_PATH", "/data/public_money.json")
        records = await load_from_file(path)
        return records, "scraper_file"

    return [], "none"


async def _persist_public_money(records: list[dict]) -> int:
    """Match AN records to games and merge into latest OddsSnapshot."""
    # Derive current week from first record's game_time (rough)
    week = _guess_week()

    async with AsyncSessionLocal() as db:
        matched_pairs = await match_all_an_records(db, records, NFL_SEASON, week)
        merged = 0
        for game, record in matched_pairs:
            try:
                snap = await merge_public_money_into_snapshot(db, game.id, record)
                if snap:
                    merged += 1
            except Exception as exc:
                logger.warning("Failed merging money for game_id=%d: %s", game.id, exc)
    return merged


def _guess_week() -> int:
    """Approximate current NFL week from today's date."""
    import math
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    season_start = datetime(now.year, 9, 7, tzinfo=timezone.utc)
    delta = (now - season_start).days
    return max(1, min(22, math.ceil((delta + 1) / 7)))
