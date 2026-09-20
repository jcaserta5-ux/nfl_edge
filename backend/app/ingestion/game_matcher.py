"""
Game Matcher
============
Matches Action Network game records to ESPN event IDs (and thus to our
NFLGame rows) using fuzzy team-abbreviation + game-time alignment.

The problem: Action Network uses its own internal game IDs and sometimes
slightly different team abbreviations than ESPN. We match by:
  1. Normalize both team abbreviations to a canonical set
  2. Find the ESPN game (NFLGame row) where home + away match
  3. Confirm the game_time is within a 4-hour window (handles timezone drift)

This runs inside the public-money Celery task after fetching AN data.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NFLGame, NFLTeam

logger = logging.getLogger(__name__)

# ── Abbreviation normalization map ────────────────────────────────────────────
# Action Network occasionally uses different abbreviations than ESPN.
# Map AN → ESPN canonical.
AN_TO_ESPN: dict[str, str] = {
    # Action Network quirks
    "JAC": "JAX",
    "WSH": "WAS",
    "WFT": "WAS",
    "OAK": "LV",    # historical
    "SD":  "LAC",   # historical
    "STL": "LAR",   # historical
    "GBP": "GB",
    "NEP": "NE",
    "KCC": "KC",
    "LVR": "LV",
    "LAR": "LAR",
    "LVS": "LV",
}

MATCH_WINDOW_HOURS = 4   # max hours between AN game_time and ESPN game_time


def normalize_abbr(abbr: str) -> str:
    """Normalize a team abbreviation to our ESPN canonical form."""
    if not abbr:
        return ""
    upper = abbr.strip().upper()
    return AN_TO_ESPN.get(upper, upper)


async def find_game_for_an_record(
    db: AsyncSession,
    an_record: dict,
    season: int,
    week: int,
) -> Optional[NFLGame]:
    """
    Given one Action Network public-money record, find the matching NFLGame row.

    Args:
        db:        Async DB session
        an_record: Normalized dict from public_money_adapter._parse_an_game()
        season:    Current NFL season year
        week:      Current week number

    Returns:
        NFLGame if matched, None if no match found.
    """
    home_abbr = normalize_abbr(an_record.get("home_team", ""))
    away_abbr = normalize_abbr(an_record.get("away_team", ""))

    if not home_abbr or not away_abbr:
        logger.warning("AN record missing team abbreviations: %s", an_record)
        return None

    # Look up team IDs
    home_result = await db.execute(
        select(NFLTeam).where(NFLTeam.abbreviation == home_abbr)
    )
    away_result = await db.execute(
        select(NFLTeam).where(NFLTeam.abbreviation == away_abbr)
    )
    home_team = home_result.scalar_one_or_none()
    away_team = away_result.scalar_one_or_none()

    if not home_team or not away_team:
        logger.warning(
            "Unknown team in AN record: home=%s away=%s", home_abbr, away_abbr
        )
        return None

    # Query by season + week + teams (most reliable)
    result = await db.execute(
        select(NFLGame).where(
            and_(
                NFLGame.season == season,
                NFLGame.week == week,
                NFLGame.home_team_id == home_team.id,
                NFLGame.away_team_id == away_team.id,
            )
        )
    )
    game = result.scalar_one_or_none()
    if game:
        return game

    # Fallback: match by team IDs + time window (ignores week, handles playoff edge cases)
    an_time = _parse_time(an_record.get("game_time", ""))
    if an_time:
        window_start = an_time - timedelta(hours=MATCH_WINDOW_HOURS)
        window_end   = an_time + timedelta(hours=MATCH_WINDOW_HOURS)
        result = await db.execute(
            select(NFLGame).where(
                and_(
                    NFLGame.home_team_id == home_team.id,
                    NFLGame.away_team_id == away_team.id,
                    NFLGame.game_time >= window_start,
                    NFLGame.game_time <= window_end,
                )
            )
        )
        game = result.scalar_one_or_none()
        if game:
            logger.debug(
                "Matched AN record to game_id=%d via time window fallback", game.id
            )
            return game

    logger.warning(
        "No NFLGame match for AN record: %s @ %s (season=%s week=%s)",
        away_abbr, home_abbr, season, week,
    )
    return None


async def match_all_an_records(
    db: AsyncSession,
    an_records: list[dict],
    season: int,
    week: int,
) -> list[tuple[NFLGame, dict]]:
    """
    Match a list of AN records to NFLGame rows.
    Returns list of (game, an_record) pairs for successfully matched games.
    """
    matched: list[tuple[NFLGame, dict]] = []
    for record in an_records:
        game = await find_game_for_an_record(db, record, season, week)
        if game:
            matched.append((game, record))
    logger.info(
        "AN↔ESPN matching: %d/%d records matched", len(matched), len(an_records)
    )
    return matched


def _parse_time(time_str: str) -> Optional[datetime]:
    """Parse an ISO-8601 string to a timezone-aware datetime."""
    if not time_str:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(time_str.replace("Z", "+00:00") if time_str.endswith("Z") else time_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    logger.warning("Could not parse game_time: %s", time_str)
    return None
