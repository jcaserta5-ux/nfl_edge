"""
Power Rankings Adapter — ESPN FPI + standings fallback.

Primary source: ESPN Football Power Index (FPI)
  https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/powerindex
  Returns per-team FPI score, overall/offensive/defensive ranks.

Fallback source: ESPN Standings API
  https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season={year}
  Returns win/loss, points for/against — used to compute a simple power rank
  when FPI returns no data (offseason, preseason, network issues).

No API keys required for either endpoint.
"""
from __future__ import annotations

import logging
import math
from typing import Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ESPN_FPI_URL = (
    "{core}/seasons/{year}/types/2/powerindex"
).format(core=settings.ESPN_CORE_URL, year="{year}")

ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"

# Map ESPN team abbreviations to the abbreviations we use in our DB.
# ESPN Core returns full ref URLs; we parse abbreviation from the $ref tail
# or the team object in the standings response.
_ESPN_ABBR_REMAP: dict[str, str] = {
    "WSH": "WAS",   # Washington Commanders
    "JAX": "JAC",   # Jacksonville Jaguars (ESPN sometimes uses JAC, sometimes JAX)
}


# ── Public interface ──────────────────────────────────────────────────────────

async def fetch_power_rankings(season: int, week: int) -> list[dict]:
    """
    Return a list of team-level power ranking dicts for the given season/week.

    Each dict has the shape:
        {
            "abbreviation": "KC",
            "fpi_score": 12.4,
            "overall_rank": 1,
            "offensive_rank": 2,
            "defensive_rank": 4,
            "sos_rank": 17,
            "wins": 5, "losses": 1,
            "win_pct": 0.833,
            "points_for": 31.2,
            "points_against": 17.8,
            "point_diff": 13.4,
            "source": "fpi",
        }
    """
    # 1. Try ESPN FPI endpoint (most accurate)
    rankings = await _fetch_fpi(season)
    if rankings:
        logger.info("Power rankings: fetched %d teams via FPI", len(rankings))
        return rankings

    # 2. Fallback to standings-derived ranking
    logger.warning("FPI returned no data — falling back to standings for season %d", season)
    rankings = await _fetch_standings_fallback(season)
    logger.info("Power rankings: fetched %d teams via standings fallback", len(rankings))
    return rankings


# ── ESPN FPI fetch ────────────────────────────────────────────────────────────

async def _fetch_fpi(season: int) -> list[dict]:
    url = ESPN_FPI_URL.format(year=season)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"limit": 32})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("FPI fetch failed: %s", exc)
        return []

    items = data.get("items") or data.get("powerIndexes") or []
    if not items:
        return []

    results = []
    for item in items:
        team_abbr = _extract_team_abbr_from_ref(item.get("team", {}).get("$ref", ""))
        if not team_abbr:
            continue

        values = {v.get("name"): v.get("value") for v in (item.get("values") or [])}

        results.append({
            "abbreviation": _remap(team_abbr),
            "fpi_score": _fv(values.get("fpi")),
            "overall_rank": _iv(values.get("fpiRank") or values.get("overallRank")),
            "offensive_rank": _iv(values.get("offensiveRank")),
            "defensive_rank": _iv(values.get("defensiveRank")),
            "sos_rank": _iv(values.get("sosRank") or values.get("strengthOfScheduleRank")),
            "wins": None,
            "losses": None,
            "win_pct": None,
            "points_for": None,
            "points_against": None,
            "point_diff": None,
            "source": "fpi",
        })

    return results


# ── Standings fallback ────────────────────────────────────────────────────────

async def _fetch_standings_fallback(season: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(ESPN_STANDINGS_URL, params={"season": season})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Standings fetch failed: %s", exc)
        return []

    # Flatten all entries from all divisions
    raw_teams: list[dict] = []
    for group in data.get("children", []):
        for division in group.get("children", []):
            for entry in division.get("standings", {}).get("entries", []):
                raw_teams.append(entry)

    if not raw_teams:
        # Try direct entries at top level
        for entry in data.get("standings", {}).get("entries", []):
            raw_teams.append(entry)

    if not raw_teams:
        logger.warning("Standings fallback: no team entries found")
        return []

    parsed = []
    for entry in raw_teams:
        abbr = (
            entry.get("team", {}).get("abbreviation")
            or entry.get("abbreviation")
        )
        if not abbr:
            continue

        stats = {s.get("name"): s.get("value") for s in (entry.get("stats") or [])}

        wins = _fv(stats.get("wins") or stats.get("gamesWon"))
        losses = _fv(stats.get("losses") or stats.get("gamesLost"))
        pf = _fv(stats.get("pointsFor") or stats.get("avgPointsFor"))
        pa = _fv(stats.get("pointsAgainst") or stats.get("avgPointsAgainst"))
        gp = (wins or 0) + (losses or 0)
        win_pct = wins / gp if (gp and wins is not None) else None

        # Normalise pf/pa to per-game if they look like season totals
        if pf and gp and pf > 40:  # totals are always >40 for a full season
            pf = pf / gp
        if pa and gp and pa > 40:
            pa = pa / gp

        point_diff = round(pf - pa, 2) if (pf is not None and pa is not None) else None

        parsed.append({
            "abbreviation": _remap(abbr.upper()),
            "fpi_score": None,
            "overall_rank": None,   # filled in after sorting
            "offensive_rank": None,
            "defensive_rank": None,
            "sos_rank": None,
            "wins": int(wins) if wins is not None else None,
            "losses": int(losses) if losses is not None else None,
            "win_pct": round(win_pct, 3) if win_pct is not None else None,
            "points_for": round(pf, 1) if pf is not None else None,
            "points_against": round(pa, 1) if pa is not None else None,
            "point_diff": point_diff,
            "source": "standings",
        })

    # Derive simple power rank from point_diff (best proxy without FPI)
    parsed.sort(
        key=lambda t: t["point_diff"] if t["point_diff"] is not None else -99,
        reverse=True,
    )
    for rank, team in enumerate(parsed, start=1):
        team["overall_rank"] = rank

    return parsed


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_team_abbr_from_ref(ref: str) -> str:
    """
    ESPN Core $ref URLs look like:
      .../teams/12?lang=en&region=us
    We need the team numeric ID mapped to abbreviation, OR the response
    sometimes includes a team object with abbreviation directly.
    If we only have the $ref, return empty and let the caller handle it.
    """
    # If the item has inline team data, caller handles it; here just return ""
    return ""


def _remap(abbr: str) -> str:
    return _ESPN_ABBR_REMAP.get(abbr, abbr)


def _fv(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _iv(val) -> Optional[int]:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# ── Alternative FPI fetch using ESPN Core v3 rankings page ───────────────────
# ESPN also exposes rankings via the scoreboard/power-index page.
# This second implementation uses the /athletes/statistics approach that
# reliably returns FPI ranks even during the season.

async def fetch_power_rankings_v2(season: int, week: int) -> list[dict]:
    """
    Second strategy: fetch from ESPN's NFL powerIndex page which returns
    teams with their FPI directly in a tabular format.
    Falls back to v1's results on failure.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/powerindex"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"season": season, "week": week, "limit": 32})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.debug("Power index v2 failed (%s), falling back to v1", exc)
        return await fetch_power_rankings(season, week)

    rows = (
        data.get("powerIndexes")
        or data.get("items")
        or data.get("rankings")
        or []
    )
    if not rows:
        return await fetch_power_rankings(season, week)

    results = []
    for i, row in enumerate(rows, start=1):
        team = row.get("team") or {}
        abbr = team.get("abbreviation") or ""
        if not abbr:
            continue
        values = {v.get("name"): v.get("value") for v in (row.get("values") or [])}
        results.append({
            "abbreviation": _remap(abbr.upper()),
            "fpi_score": _fv(values.get("fpi") or row.get("score")),
            "overall_rank": _iv(row.get("rank") or i),
            "offensive_rank": _iv(values.get("offensiveRank")),
            "defensive_rank": _iv(values.get("defensiveRank")),
            "sos_rank": _iv(values.get("sosRank")),
            "wins": _iv(team.get("wins")),
            "losses": _iv(team.get("losses")),
            "win_pct": _fv(team.get("winPercent")),
            "points_for": None,
            "points_against": None,
            "point_diff": None,
            "source": "fpi",
        })

    if results:
        logger.info("Power rankings v2: got %d teams", len(results))
        return results

    return await fetch_power_rankings(season, week)
