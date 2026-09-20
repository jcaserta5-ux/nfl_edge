"""
Redis caching layer.
Simple JSON cache with TTL. Used by API route handlers to avoid
hammering the DB on every frontend poll.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def cache_get(key: str) -> Optional[Any]:
    try:
        raw = await get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Cache GET failed for %s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    try:
        await get_redis().setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        logger.warning("Cache SET failed for %s: %s", key, exc)


async def cache_delete(key: str) -> None:
    try:
        await get_redis().delete(key)
    except Exception as exc:
        logger.warning("Cache DELETE failed for %s: %s", key, exc)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern (e.g. 'games:*')."""
    try:
        r = get_redis()
        keys = [k async for k in r.scan_iter(pattern)]
        if keys:
            await r.delete(*keys)
    except Exception as exc:
        logger.warning("Cache DELETE pattern %s failed: %s", pattern, exc)


# ── Cache key helpers ─────────────────────────────────────────────────────────

def games_list_key(season: int, week: int) -> str:
    return f"games:list:{season}:{week}"


def game_detail_key(game_id: int) -> str:
    return f"games:detail:{game_id}"


def odds_history_key(game_id: int) -> str:
    return f"games:odds_history:{game_id}"


# TTLs (seconds)
GAMES_LIST_TTL   = 60    # 1 minute — updates frequently
GAME_DETAIL_TTL  = 30    # 30 seconds
ODDS_HISTORY_TTL = 120   # 2 minutes
