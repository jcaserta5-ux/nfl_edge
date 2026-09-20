"""
Power Rankings Adapter – ESPN Core API (sports.core.api.espn.com).
site.api.espn.com is avoided – Akamai blocks server-side requests.
FPI only available from ~week 4; standings fallback always works.
"""
from __future__ import annotations
import asyncio, logging, math
from typing import Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
_REMAP = {"WSH":"WAS","JAX":"JAC","LVR":"LV"}

async def fetch_power_rankings_v2(season: int, week: int) -> list[dict]:
    return await fetch_power_rankings(season, week)

async def fetch_power_rankings(season: int, week: int) -> list[dict]:
    r = await _fetch_fpi(season)
    if r:
        return r
    logger.warning("FPI unavailable – using standings fallback season=%d", season)
    return await _fetch_standings_fallback(season)

async def _fetch_fpi(season: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.get(f"{CORE}/seasons/{season}/types/2/powerindex", params={"limit":32})
            resp.raise_for_status(); data = resp.json()
    except Exception as e:
        logger.warning("FPI failed: %s", e); return []
    items = data.get("items") or []
    if not items: return []
    out = []
    for item in items:
        team = item.get("team") or {}
        abbr = team.get("abbreviation") or ""
        if not abbr: continue
        vals = {v["name"]: v.get("value") for v in (item.get("values") or [])}
        out.append({"abbreviation": _remap(abbr), "fpi_score": _fv(vals.get("fpi")),
            "overall_rank": _iv(vals.get("fpiRank")), "offensive_rank": _iv(vals.get("offensiveRank")),
            "defensive_rank": _iv(vals.get("defensiveRank")), "sos_rank": _iv(vals.get("sosRank")),
            "wins":None,"losses":None,"win_pct":None,"points_for":None,"points_against":None,"point_diff":None,"source":"fpi"})
    return out

async def _fetch_standings_fallback(season: int) -> list[dict]:
    # Try standings/0 (overall group) first
    url = f"{CORE}/seasons/{season}/types/2/standings/0"
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            resp = await c.get(url); resp.raise_for_status(); data = resp.json()
    except Exception as e:
        logger.warning("standings/0 failed: %s", e); return []

    logger.debug("standings/0 keys: %s", list(data.keys()))
    entries = data.get("entries") or data.get("standings", {}).get("entries") or []

    # If /standings/0 has no entries, walk the group $refs
    if not entries:
        logger.warning("standings/0 empty – walking group refs. keys=%s", list(data.keys()))
        entries = await _entries_via_groups(season)

    if not entries:
        logger.warning("No standings entries for season=%d", season); return []

    parsed = []
    for e in entries:
        team = e.get("team") or {}
        abbr = team.get("abbreviation") or ""
        if not abbr: continue
        stats = {s["name"]: s.get("value") for s in (e.get("stats") or [])}
        wins   = _fv(stats.get("wins") or stats.get("gamesWon"))
        losses = _fv(stats.get("losses") or stats.get("gamesLost"))
        pf     = _fv(stats.get("pointsFor") or stats.get("totalPointsFor"))
        pa     = _fv(stats.get("pointsAgainst") or stats.get("totalPointsAgainst"))
        gp     = (wins or 0) + (losses or 0)
        wpc    = wins/gp if (gp and wins is not None) else None
        if pf and gp and pf > 40: pf = round(pf/gp, 1)
        if pa and gp and pa > 40: pa = round(pa/gp, 1)
        pd = round(pf-pa, 2) if (pf is not None and pa is not None) else None
        parsed.append({"abbreviation":_remap(abbr),"fpi_score":None,"overall_rank":None,
            "offensive_rank":None,"defensive_rank":None,"sos_rank":None,
            "wins":int(wins) if wins is not None else None,
            "losses":int(losses) if losses is not None else None,
            "win_pct":round(wpc,3) if wpc is not None else None,
            "points_for":round(pf,1) if pf is not None else None,
            "points_against":round(pa,1) if pa is not None else None,
            "point_diff":pd,"source":"standings"})

    parsed.sort(key=lambda t: t["point_diff"] if t["point_diff"] is not None else -999, reverse=True)
    for rank, t in enumerate(parsed, 1): t["overall_rank"] = rank
    logger.info("Standings: ranked %d teams season=%d", len(parsed), season)
    return parsed

async def _entries_via_groups(season: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(f"{CORE}/seasons/{season}/types/2/standings", params={"limit":10})
            r.raise_for_status(); groups = r.json().get("items") or []
    except Exception as e:
        logger.warning("standings group list failed: %s", e); return []
    entries = []
    async with httpx.AsyncClient(timeout=20.0) as c:
        for g in groups:
            ref = g.get("$ref") or ""
            if not ref: continue
            try:
                r = await c.get(ref); r.raise_for_status(); gd = r.json()
                for e in (gd.get("entries") or gd.get("standings",{}).get("entries") or []):
                    entries.append(e)
            except Exception: continue
    return entries

def _remap(a): return _REMAP.get(a.upper(), a.upper())
def _fv(v):
    try: return float(v) if v is not None else None
    except: return None
def _iv(v):
    try: return int(v) if v is not None else None
    except: return None
