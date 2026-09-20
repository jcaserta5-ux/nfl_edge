"""
Public Money Adapter
====================
Fetches NFL public betting percentages and bet counts from free sources.

Source priority:
  1. Action Network (undocumented public API, no key required)
       https://api.actionnetwork.com/web/v1/scoreboard/nfl
       Returns: bet %, money %, bet counts per game per market
  2. Your own scraper (file drop or HTTP endpoint) — same format as before

Action Network API notes
------------------------
- No API key required. Rate-limit is lenient (~1 req/5 min is safe).
- Returns 14-day lookahead for upcoming NFL games.
- Consensus endpoint gives both bet % AND money % for spread/ML/total.
- ESPN has NO public money data — Action Network is the best free source.
- Odds in the AN response are also present but we rely on ESPN for those.

Response shape (Action Network /v1/scoreboard/nfl):
  {
    "games": [
      {
        "id": 12345,
        "teams": { "home": {"abbr": "NE"}, "away": {"abbr": "BUF"} },
        "start_time": "2026-09-21T17:00:00Z",
        "consensus": [
          {
            "type": "spread",
            "home_percent": 42,     <- % of bets on home spread
            "away_percent": 58,
            "home_money": 36,       <- % of dollars on home spread
            "away_money": 64,
            "bet_count": 14200
          },
          { "type": "total",
            "home_percent": 63,    <- over %
            "away_percent": 37,    <- under %
            "bet_count": 11800
          },
          { "type": "moneyline",
            "home_percent": 38,
            "away_percent": 62,
            "bet_count": 9300
          }
        ]
      }
    ]
  }

Note: field names above are representative — actual AN field names mapped
in _parse_an_game() below using confirmed community documentation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ── Action Network endpoints ──────────────────────────────────────────────────

AN_BASE = "https://api.actionnetwork.com/web/v1"
AN_SCOREBOARD = f"{AN_BASE}/scoreboard/nfl"
AN_GAME       = f"{AN_BASE}/games/{{game_id}}/consensus"

AN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.actionnetwork.com/nfl/public-betting",
    "Origin": "https://www.actionnetwork.com",
}

# bookIds: 15 = DraftKings on Action Network
AN_PARAMS = {
    "period": "game",
    "bookIds": "15",
}


# ── Primary: Action Network ───────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
async def fetch_action_network() -> list[dict]:
    """
    Fetch NFL public betting percentages from Action Network's free API.
    Returns a list of normalized public-money records, one per game.
    No API key required.
    """
    async with httpx.AsyncClient(timeout=20, headers=AN_HEADERS) as client:
        resp = await client.get(AN_SCOREBOARD, params=AN_PARAMS)
        resp.raise_for_status()
        data = resp.json()

    games_raw = data.get("games", [])
    logger.info("Action Network returned %d games", len(games_raw))

    results: list[dict] = []
    for game in games_raw:
        parsed = _parse_an_game(game)
        if parsed:
            results.append(parsed)
    return results


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
async def fetch_action_network_game(game_id: int) -> Optional[dict]:
    """Fetch consensus data for a single Action Network game ID."""
    url = AN_GAME.format(game_id=game_id)
    async with httpx.AsyncClient(timeout=15, headers=AN_HEADERS) as client:
        resp = await client.get(url, params=AN_PARAMS)
        resp.raise_for_status()
        data = resp.json()
    return _parse_an_game(data.get("game", {}))


def _parse_an_game(game: dict) -> Optional[dict]:
    """
    Parse a single Action Network game response into our normalized format.

    Action Network uses several field naming conventions across endpoint
    versions; this handles both snake_case and camelCase variants.
    """
    if not game:
        return None

    try:
        # Team abbreviations
        teams = game.get("teams", {})
        home_info = teams.get("home", {})
        away_info = teams.get("away", {})
        home_abbr = (
            home_info.get("abbr")
            or home_info.get("alias")
            or home_info.get("abbreviation", "")
        ).upper()
        away_abbr = (
            away_info.get("abbr")
            or away_info.get("alias")
            or away_info.get("abbreviation", "")
        ).upper()

        # Game time
        game_time = game.get("start_time") or game.get("startTime") or game.get("scheduled", "")

        # Action Network game ID (for matching to ESPN event later)
        an_game_id = game.get("id")

        # ── Parse consensus markets ───────────────────────────────────────────
        # AN returns consensus as a list keyed by "type": spread/total/moneyline
        consensus_list = game.get("consensus", [])

        # Fallback: some AN endpoints put it directly under the game object
        if not consensus_list:
            consensus_list = game.get("markets", [])

        spread_data = _find_market(consensus_list, "spread")
        total_data  = _find_market(consensus_list, "total")
        ml_data     = _find_market(consensus_list, "moneyline")

        result: dict = {
            "an_game_id": an_game_id,
            "home_team": home_abbr,
            "away_team": away_abbr,
            "game_time": game_time,
            # Spread bets
            "home_spread_pct": _pct(
                spread_data.get("home_percent")
                or spread_data.get("homePercent")
            ),
            "away_spread_pct": _pct(
                spread_data.get("away_percent")
                or spread_data.get("awayPercent")
            ),
            # Spread money
            "home_money_pct": _pct(
                spread_data.get("home_money")
                or spread_data.get("homeMoney")
                or spread_data.get("home_money_percent")
            ),
            "away_money_pct": _pct(
                spread_data.get("away_money")
                or spread_data.get("awayMoney")
                or spread_data.get("away_money_percent")
            ),
            # Total (over/under)
            "over_pct": _pct(
                total_data.get("home_percent")   # AN uses "home" for over
                or total_data.get("homePercent")
                or total_data.get("over_percent")
            ),
            "under_pct": _pct(
                total_data.get("away_percent")   # AN uses "away" for under
                or total_data.get("awayPercent")
                or total_data.get("under_percent")
            ),
            # Moneyline
            "home_ml_pct": _pct(
                ml_data.get("home_percent") or ml_data.get("homePercent")
            ),
            "away_ml_pct": _pct(
                ml_data.get("away_percent") or ml_data.get("awayPercent")
            ),
            # Bet count (use spread market count as primary, fall back to total)
            "total_bet_count": (
                spread_data.get("bet_count")
                or spread_data.get("betCount")
                or total_data.get("bet_count")
                or total_data.get("betCount")
            ),
        }

        # Derive missing spread pcts from each other if one side is known
        result = _fill_complements(result)
        return result

    except Exception as exc:
        logger.warning(
            "Failed parsing AN game (id=%s): %s",
            game.get("id"), exc, exc_info=True
        )
        return None


def _find_market(consensus_list: list[dict], market_type: str) -> dict:
    """Return the first consensus entry matching the given market type."""
    for m in consensus_list:
        t = (m.get("type") or m.get("market_type") or "").lower()
        if t == market_type:
            return m
    return {}


def _fill_complements(r: dict) -> dict:
    """If only one side of a 2-side pct pair is known, compute the other."""
    pairs = [
        ("home_spread_pct", "away_spread_pct"),
        ("home_money_pct", "away_money_pct"),
        ("over_pct", "under_pct"),
        ("home_ml_pct", "away_ml_pct"),
    ]
    for a, b in pairs:
        if r.get(a) is not None and r.get(b) is None:
            r[b] = round(100.0 - r[a], 1)
        elif r.get(b) is not None and r.get(a) is None:
            r[a] = round(100.0 - r[b], 1)
    return r


# ── Fallback: file or HTTP endpoint (your existing scraper) ───────────────────

async def load_from_file(path: str | Path) -> list[dict]:
    """
    Read a JSON file exported by your own scraper and return normalized
    public-money records. Accepts both list format and {"games": [...]} format.
    """
    path = Path(path)
    if not path.exists():
        logger.warning("Public money scraper file not found: %s", path)
        return []
    try:
        with open(path) as f:
            raw = json.load(f)
        records = raw if isinstance(raw, list) else raw.get("games", [])
        return [_normalize_scraper_record(r) for r in records if r]
    except Exception as exc:
        logger.error("Failed loading public money file %s: %s", path, exc)
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
async def fetch_from_endpoint(url: str, api_key: Optional[str] = None) -> list[dict]:
    """Poll your own scraper HTTP endpoint for public money data."""
    headers = dict(AN_HEADERS)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        raw = resp.json()
    records = raw if isinstance(raw, list) else raw.get("games", [])
    return [_normalize_scraper_record(r) for r in records if r]


def _normalize_scraper_record(r: dict) -> dict:
    """Normalize your scraper's output to our internal format."""
    return {
        "an_game_id": None,
        "home_team": str(r.get("home_team", "")),
        "away_team": str(r.get("away_team", "")),
        "game_time": str(r.get("game_time", "")),
        "home_spread_pct": _pct(r.get("home_spread_pct")),
        "away_spread_pct": _pct(r.get("away_spread_pct")),
        "over_pct":        _pct(r.get("over_pct")),
        "under_pct":       _pct(r.get("under_pct")),
        "home_ml_pct":     _pct(r.get("home_ml_pct")),
        "away_ml_pct":     _pct(r.get("away_ml_pct")),
        "home_money_pct":  _pct(r.get("home_money_pct")),
        "away_money_pct":  _pct(r.get("away_money_pct")),
        "total_bet_count": r.get("total_bet_count"),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(val) -> Optional[float]:
    if val is None:
        return None
    try:
        v = float(val)
        return round(v, 1)
    except (TypeError, ValueError):
        return None
