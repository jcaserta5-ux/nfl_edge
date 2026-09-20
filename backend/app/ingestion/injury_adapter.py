"""
Injury Report Adapter — ESPN Injuries API.

Endpoint (no auth required):
  GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries

Returns all active injury designations across all 32 teams.
Also supports per-team: .../nfl/teams/{team_id}/injuries

Key player detection:
  - QB is always flagged (is_qb=True, is_key_player=True)
  - RB, WR, TE, OT, iOL, LB, DL, DB at starting/notable level flagged as key
  - "Out" status carries 3x the edge-score weight vs "Questionable"

Status priority (worst-to-best):
  Out > Doubtful > Questionable > Probable

No API keys required.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

ESPN_INJURIES_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
)

# Positions that meaningfully affect our edge scoring
_KEY_POSITIONS = {
    "QB",                                       # always key
    "RB", "WR", "TE",                           # skill positions
    "LT", "LG", "C", "RG", "RT", "OT", "OL",  # offensive line
    "DE", "DT", "NT", "EDGE",                   # pass rush
    "LB", "MLB", "ILB", "OLB",                  # linebackers
    "CB", "S", "SS", "FS",                      # secondary
    "K", "P",                                   # specialists (minor impact)
}

_STATUS_WEIGHTS = {
    "Out": 3.0,
    "Doubtful": 2.0,
    "Questionable": 1.0,
    "Probable": 0.25,
    "IR": 3.0,
    "PUP": 2.5,
    "NFI": 1.5,
}

# ESPN abbreviation → our DB abbreviation
_ABBR_REMAP: dict[str, str] = {
    "WSH": "WAS",
    "JAX": "JAC",
}


# ── Public interface ──────────────────────────────────────────────────────────

async def fetch_injuries() -> list[dict]:
    """
    Fetch all current NFL injury designations from ESPN.

    Returns a flat list of player-level injury dicts:
        {
            "team_abbreviation": "KC",
            "espn_athlete_id": "4241457",
            "athlete_name": "Patrick Mahomes",
            "position": "QB",
            "jersey_number": "15",
            "status": "Questionable",
            "injury_type": "Ankle",
            "is_qb": True,
            "is_key_player": True,
            "reported_at": datetime(2026, 9, 18, ...),
        }
    """
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(ESPN_INJURIES_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("ESPN injuries fetch failed: %s", exc)
        return []

    results: list[dict] = []
    for team_entry in data.get("injuries", []):
        team = team_entry.get("team", {})
        team_abbr = _remap(team.get("abbreviation", "").upper())
        if not team_abbr:
            continue

        for inj in team_entry.get("injuries", []):
            athlete = inj.get("athlete", {})
            position_obj = athlete.get("position", {})
            position = (position_obj.get("abbreviation") or "").upper()

            status_raw = inj.get("status", "") or ""
            # ESPN sometimes returns "Questionable (Knee)" — split it
            status = status_raw.split("(")[0].strip()
            if not status:
                continue

            # Injury type from the type sub-object
            injury_type = (
                (inj.get("type") or {}).get("description")
                or inj.get("injury", {}).get("type", {}).get("description")
                or inj.get("longComment")
                or ""
            )

            # Date
            reported_at = _parse_date(inj.get("date"))

            is_qb = position == "QB"
            is_key = is_qb or position in _KEY_POSITIONS

            results.append({
                "team_abbreviation": team_abbr,
                "espn_athlete_id": str(athlete.get("id", "")) or None,
                "athlete_name": athlete.get("fullName") or athlete.get("displayName") or "Unknown",
                "position": position or None,
                "jersey_number": athlete.get("jersey") or None,
                "status": _normalise_status(status),
                "injury_type": injury_type[:64] if injury_type else None,
                "is_qb": is_qb,
                "is_key_player": is_key,
                "reported_at": reported_at,
            })

    logger.info("Injury adapter: parsed %d player records", len(results))
    return results


async def fetch_injuries_for_team(espn_team_id: str) -> list[dict]:
    """
    Per-team injury fetch — used as a targeted refresh.
    Returns same schema as fetch_injuries().
    """
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        f"/teams/{espn_team_id}/injuries"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Per-team injury fetch for id=%s failed: %s", espn_team_id, exc)
        return []

    results: list[dict] = []
    team_abbr = _remap(
        (data.get("team", {}).get("abbreviation") or "").upper()
    )

    for inj in data.get("injuries", []):
        athlete = inj.get("athlete", {})
        position = (athlete.get("position", {}).get("abbreviation") or "").upper()
        status = (inj.get("status") or "").split("(")[0].strip()
        if not status:
            continue
        injury_type = (
            (inj.get("type") or {}).get("description")
            or inj.get("injury", {}).get("type", {}).get("description")
            or ""
        )
        is_qb = position == "QB"
        results.append({
            "team_abbreviation": team_abbr,
            "espn_athlete_id": str(athlete.get("id", "")) or None,
            "athlete_name": athlete.get("fullName") or "Unknown",
            "position": position or None,
            "jersey_number": athlete.get("jersey") or None,
            "status": _normalise_status(status),
            "injury_type": injury_type[:64] if injury_type else None,
            "is_qb": is_qb,
            "is_key_player": is_qb or position in _KEY_POSITIONS,
            "reported_at": _parse_date(inj.get("date")),
        })
    return results


# ── Edge impact helpers ───────────────────────────────────────────────────────

def compute_injury_impact(
    home_injuries: list[dict],
    away_injuries: list[dict],
) -> tuple[float, list[str]]:
    """
    Given the injury records for both teams in a game, compute a 0–100
    impact score and generate narrative notes.

    Higher score = more significant injury advantage (one team is significantly
    more impacted by injuries than the other). A balanced game returns ~0.

    Returns:
        (score_0_to_100, list_of_note_strings)
    """
    home_impact = _team_injury_impact(home_injuries)
    away_impact = _team_injury_impact(away_injuries)

    net = away_impact - home_impact    # positive → away team more banged up
    raw_score = min(abs(net) / 8.0 * 100, 100)
    notes: list[str] = []

    # QB injury notes (highest priority)
    home_qb_out = any(i["is_qb"] and i["status"] in ("Out", "Doubtful") for i in home_injuries)
    away_qb_out = any(i["is_qb"] and i["status"] in ("Out", "Doubtful") for i in away_injuries)
    home_qb_q = any(i["is_qb"] and i["status"] == "Questionable" for i in home_injuries)
    away_qb_q = any(i["is_qb"] and i["status"] == "Questionable" for i in away_injuries)

    if home_qb_out:
        qb = next(i for i in home_injuries if i["is_qb"] and i["status"] in ("Out", "Doubtful"))
        notes.append(f"🚨 {qb['athlete_name']} ({qb['status']}) — home QB concern")
    if away_qb_out:
        qb = next(i for i in away_injuries if i["is_qb"] and i["status"] in ("Out", "Doubtful"))
        notes.append(f"🚨 {qb['athlete_name']} ({qb['status']}) — away QB concern")
    if home_qb_q and not home_qb_out:
        qb = next(i for i in home_injuries if i["is_qb"] and i["status"] == "Questionable")
        notes.append(f"⚠️ {qb['athlete_name']} (Questionable) — home QB watch")
    if away_qb_q and not away_qb_out:
        qb = next(i for i in away_injuries if i["is_qb"] and i["status"] == "Questionable")
        notes.append(f"⚠️ {qb['athlete_name']} (Questionable) — away QB watch")

    # Key player counts
    home_key_out = sum(
        1 for i in home_injuries
        if i["is_key_player"] and i["status"] in ("Out", "Doubtful")
    )
    away_key_out = sum(
        1 for i in away_injuries
        if i["is_key_player"] and i["status"] in ("Out", "Doubtful")
    )

    if home_key_out >= 2:
        notes.append(f"Home team missing {home_key_out} key players (Out/Doubtful)")
    if away_key_out >= 2:
        notes.append(f"Away team missing {away_key_out} key players (Out/Doubtful)")

    return round(raw_score, 1), notes


def _team_injury_impact(injuries: list[dict]) -> float:
    """
    Compute a raw impact number for one team's injury list.
    QBs are worth 5x a regular key player in the formula.
    """
    score = 0.0
    for inj in injuries:
        weight = _STATUS_WEIGHTS.get(inj.get("status", ""), 0.0)
        if inj.get("is_qb"):
            score += weight * 5.0
        elif inj.get("is_key_player"):
            score += weight * 1.0
    return score


# ── Private helpers ───────────────────────────────────────────────────────────

def _normalise_status(raw: str) -> str:
    """Map ESPN status strings to our canonical set."""
    mapping = {
        "out": "Out",
        "doubtful": "Doubtful",
        "questionable": "Questionable",
        "probable": "Probable",
        "injured reserve": "IR",
        "ir": "IR",
        "pup": "PUP",
        "physically unable to perform": "PUP",
        "nfi": "NFI",
        "not injury related": "NFI",
    }
    return mapping.get(raw.lower(), raw)


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _remap(abbr: str) -> str:
    return _ABBR_REMAP.get(abbr, abbr)
