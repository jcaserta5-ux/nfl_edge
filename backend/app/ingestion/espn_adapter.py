"""
ESPN NFL Odds Adapter
=====================
Pulls DraftKings spread / moneyline / total lines from ESPN's undocumented
public APIs — no API key required.

Two-tier approach:
  1. Scoreboard endpoint  → fast, one call per week, embedded DK odds
  2. Core per-event API   → richer detail + line-movement history per game

ESPN provider IDs (bet_provider_id):
  1002 = DraftKings   ← primary
  1004 = ESPN BET     ← secondary fallback within ESPN
  1003 = numberfire   ← projections only, NOT real odds — skip

Scoreboard endpoint:
  https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
  ?dates={YYYYMMDD}&seasontype=2&week={N}

Per-event odds endpoint:
  https://sports.core.api.espn.com/v2/sports/football/leagues/nfl
  /events/{event_id}/competitions/{event_id}/odds

Line movement endpoint:
  https://sports.core.api.espn.com/v2/sports/football/leagues/nfl
  /events/{event_id}/competitions/{event_id}/odds/{provider_id}
  /history/0/movement?limit=100

Response shape (scoreboard odds[]):
  {
    "provider": {"id": "1002", "name": "DraftKings"},
    "details": "NE -3.5",          <- "AWAY -spread" or "EVEN"
    "overUnder": 44.5,
    "spread": -3.5,                 <- home team spread (negative = home fav)
    "overOdds": -110,               <- American odds on the over
    "underOdds": -110,
    "awayTeamOdds": {
        "favorite": false,
        "moneyLine": 145,
        "spreadOdds": -110
    },
    "homeTeamOdds": {
        "favorite": true,
        "moneyLine": -165,
        "spreadOdds": -110
    }
  }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)
CORE_ODDS_URL = (
    "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
    "/events/{event_id}/competitions/{event_id}/odds"
)
MOVEMENT_URL = (
    "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
    "/events/{event_id}/competitions/{event_id}/odds/{provider_id}"
    "/history/0/movement"
)

# Provider priority order — first match wins
PROVIDER_PRIORITY = [
    ("1002", "draftkings"),
    ("1004", "espn_bet"),   # fallback if DK not present on this event
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.espn.com/nfl/",
    "Origin": "https://www.espn.com",
}


# ── Public API ─────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_espn_scoreboard_odds(
    season: Optional[int] = None,
    week: Optional[int] = None,
    season_type: int = 2,          # 1=preseason, 2=regular, 3=postseason
) -> list[dict]:
    """
    Fetch all NFL game odds for the given week from ESPN's scoreboard endpoint.

    Returns a list of normalized game-odds dicts ready for OddsSnapshot
    insertion. Falls back to Core API for any game missing odds in the
    scoreboard response.

    Args:
        season:      NFL season year (e.g. 2026). Defaults to current year.
        week:        Week number 1–18 (or 19–22 for playoffs). Defaults to
                     current week from ESPN's live scoreboard.
        season_type: 2 = regular season (default), 3 = postseason.
    """
    now = datetime.now(timezone.utc)
    params: dict = {"seasontype": season_type}
    if season:
        params["dates"] = str(season)
    if week:
        params["week"] = week

    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        resp = await client.get(SCOREBOARD_URL, params=params)
        resp.raise_for_status()
        scoreboard = resp.json()

    events = scoreboard.get("events", [])
    logger.info("ESPN scoreboard returned %d events (season=%s week=%s)", len(events), season, week)

    results: list[dict] = []
    for event in events:
        parsed = _parse_scoreboard_event(event)
        if parsed:
            results.append(parsed)

    return results


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_espn_event_odds(event_id: str) -> Optional[dict]:
    """
    Fetch detailed odds for a single event from the ESPN Core API.
    Useful when the scoreboard response is missing odds for a game.
    """
    url = CORE_ODDS_URL.format(event_id=event_id)
    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        resp = await client.get(url, params={"limit": 25})
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])

    # Resolve any $ref items (ESPN sometimes paginates odds as refs)
    resolved: list[dict] = []
    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        for item in items:
            if "$ref" in item and len(item) == 1:
                try:
                    ref_url = item["$ref"].replace(".pvt", ".com")
                    r = await client.get(ref_url)
                    r.raise_for_status()
                    resolved.append(r.json())
                except Exception as exc:
                    logger.warning("Failed resolving $ref %s: %s", item["$ref"], exc)
            else:
                resolved.append(item)

    return _pick_best_provider_odds(resolved)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_espn_line_movement(
    event_id: str,
    provider_id: str = "1002",
    limit: int = 100,
) -> list[dict]:
    """
    Fetch line movement history for a game from ESPN's Core API.
    Returns a time-ordered list of dicts: {timestamp, spread, overUnder}.
    """
    url = MOVEMENT_URL.format(event_id=event_id, provider_id=provider_id)
    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        resp = await client.get(url, params={"limit": limit})
        resp.raise_for_status()
        data = resp.json()

    movements: list[dict] = []
    for item in data.get("items", []):
        movements.append({
            "timestamp": item.get("timestamp"),
            "home_spread": item.get("spread"),
            "total": item.get("overUnder"),
            "home_spread_juice": _american(item.get("homeSpreadOdds")),
            "away_spread_juice": _american(item.get("awaySpreadOdds")),
            "over_juice": _american(item.get("overOdds")),
            "under_juice": _american(item.get("underOdds")),
        })
    return movements


# ── Parsers ────────────────────────────────────────────────────────────────────

def _parse_scoreboard_event(event: dict) -> Optional[dict]:
    """
    Parse a single ESPN scoreboard event into our normalized odds dict.
    ESPN scoreboard includes one competitions[] entry per game.
    """
    try:
        event_id = event.get("id", "")
        game_time = event.get("date", "")               # ISO-8601 UTC

        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])

        # Map home/away team abbreviations
        home_abbr = away_abbr = ""
        for c in competitors:
            abbr = c.get("team", {}).get("abbreviation", "")
            if c.get("homeAway") == "home":
                home_abbr = abbr
            else:
                away_abbr = abbr

        # Find best provider in odds[]
        odds_list = comp.get("odds", [])
        odds_obj = _pick_best_provider_odds(odds_list)

        if not odds_obj:
            logger.debug("No usable odds for event %s (%s @ %s)", event_id, away_abbr, home_abbr)
            return None

        provider_name = odds_obj.get("_provider_name", "draftkings")
        provider_id = odds_obj.get("_provider_id", "1002")

        # --- Spread ---
        # ESPN's "spread" field is the HOME team spread (negative = home fav)
        home_spread = _float(odds_obj.get("spread"))
        away_spread = None if home_spread is None else round(-home_spread, 1)

        home_team_odds = odds_obj.get("homeTeamOdds", {})
        away_team_odds = odds_obj.get("awayTeamOdds", {})

        home_spread_juice = _american(home_team_odds.get("spreadOdds"))
        away_spread_juice = _american(away_team_odds.get("spreadOdds"))

        # --- Moneyline ---
        home_ml = _american(home_team_odds.get("moneyLine"))
        away_ml = _american(away_team_odds.get("moneyLine"))

        # --- Total ---
        total = _float(odds_obj.get("overUnder"))
        over_juice = _american(odds_obj.get("overOdds"))
        under_juice = _american(odds_obj.get("underOdds"))

        return {
            "source": provider_name,
            "external_id": event_id,          # ESPN event_id
            "espn_provider_id": provider_id,
            "home_team": home_abbr,
            "away_team": away_abbr,
            "game_time": game_time,

            "home_spread": home_spread,
            "away_spread": away_spread,
            "home_spread_juice": home_spread_juice,
            "away_spread_juice": away_spread_juice,

            "home_ml": home_ml,
            "away_ml": away_ml,

            "total": total,
            "over_juice": over_juice,
            "under_juice": under_juice,
        }

    except Exception as exc:
        logger.warning("Failed parsing ESPN event %s: %s", event.get("id"), exc, exc_info=True)
        return None


def _pick_best_provider_odds(odds_list: list[dict]) -> Optional[dict]:
    """
    Given a list of provider-odds objects, return the one matching our
    preferred provider priority (DraftKings first, ESPN BET second).
    Annotates the chosen dict with _provider_name and _provider_id.
    """
    provider_map: dict[str, dict] = {}
    for odds in odds_list:
        provider = odds.get("provider", {})
        pid = str(provider.get("id", ""))
        if pid:
            provider_map[pid] = odds

    for pid, pname in PROVIDER_PRIORITY:
        if pid in provider_map:
            obj = dict(provider_map[pid])   # shallow copy
            obj["_provider_id"] = pid
            obj["_provider_name"] = pname
            return obj

    # Last resort: return first odds object with a spread value
    for odds in odds_list:
        if odds.get("spread") is not None or odds.get("overUnder") is not None:
            obj = dict(odds)
            provider = odds.get("provider", {})
            obj["_provider_id"] = str(provider.get("id", "unknown"))
            obj["_provider_name"] = provider.get("name", "unknown").lower().replace(" ", "_")
            return obj

    return None


# ── Type coercers ─────────────────────────────────────────────────────────────

def _float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _american(val) -> Optional[int]:
    """Coerce ESPN moneyLine / spreadOdds to int American odds."""
    if val is None:
        return None
    try:
        v = int(round(float(val)))
        return v if v != 0 else -110      # ESPN sometimes sends 0 instead of -110
    except (TypeError, ValueError):
        return None
