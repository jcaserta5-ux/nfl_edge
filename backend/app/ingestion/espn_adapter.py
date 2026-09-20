from __future__ import annotations
import asyncio, logging, re
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)
CORE_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
MOVEMENT_URL = CORE_BASE + "/events/{event_id}/competitions/{event_id}/odds/{provider_id}/history/0/movement"
_REMAP = {"WSH":"WAS","LVR":"LV"}
PROVIDER_PRIORITY = [("100","draftkings"),("1002","draftkings"),("200","espn_bet"),("1004","espn_bet")]

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_espn_scoreboard_odds(season=None, week=None, season_type=2):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    s = season or now.year
    w = week or _current_week(now)
    id_to_abbr = await _build_team_map()
    if not id_to_abbr:
        logger.error("Could not build team map"); return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(f"{CORE_BASE}/seasons/{s}/types/{season_type}/weeks/{w}/events", params={"limit":16})
            r.raise_for_status(); items = r.json().get("items") or []
    except Exception as e:
        logger.error("Week events failed: %s", e); return []
    event_refs = [i.get("$ref","") for i in items if i.get("$ref")]
    sem = asyncio.Semaphore(6)
    results = await asyncio.gather(*[_process_core_event(ref, id_to_abbr, sem) for ref in event_refs], return_exceptions=True)
    out = [r for r in results if isinstance(r, dict)]
    logger.info("Odds parsed: %d/%d", len(out), len(event_refs))
    return out

async def fetch_espn_line_movement(event_id: str, provider_id: str = "100", limit: int = 100):
    url = MOVEMENT_URL.format(event_id=event_id, provider_id=provider_id)
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(url, params={"limit":limit}); r.raise_for_status(); data = r.json()
    return [{"timestamp":i.get("timestamp"),"home_spread":i.get("spread"),"total":i.get("overUnder"),"over_juice":_american(i.get("overOdds")),"under_juice":_american(i.get("underOdds"))} for i in (data.get("items") or [])]

async def _process_core_event(ref, id_to_abbr, sem):
    async with sem:
        try:
            async with httpx.AsyncClient(timeout=12.0) as c:
                r = await c.get(ref.replace("http://","https://")); r.raise_for_status(); evt = r.json()
        except Exception as e:
            logger.debug("event ref error: %s", e); return None
    event_id = str(evt.get("id",""))
    game_time = evt.get("date","")
    comps = evt.get("competitions") or []
    if not comps: return None
    comp = comps[0]
    home_abbr = away_abbr = ""
    for c in (comp.get("competitors") or []):
        abbr = id_to_abbr.get(str(c.get("id","")), "")
        if c.get("homeAway") == "home": home_abbr = abbr
        else: away_abbr = abbr
    odds_data = comp.get("odds") or {}
    if not (isinstance(odds_data, dict) and "$ref" in odds_data): return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(odds_data["$ref"].replace("http://","https://")); r.raise_for_status()
            odds_payload = r.json()
    except Exception as e:
        logger.debug("odds ref error %s: %s", event_id, e); return None
    items = await _resolve_odds_items(odds_payload.get("items") or [])
    odds_obj = _pick_best_provider_odds(items)
    if not odds_obj: return None
    return _build_game_record(event_id, game_time, home_abbr, away_abbr, odds_obj)

async def _resolve_odds_items(items):
    resolved = []
    for item in items:
        if isinstance(item, dict) and list(item.keys()) == ["$ref"]:
            try:
                async with httpx.AsyncClient(timeout=8.0) as c:
                    r = await c.get(item["$ref"].replace("http://","https://")); resolved.append(r.json())
            except: pass
        else:
            resolved.append(item)
    return resolved

async def _build_team_map():
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(f"{CORE_BASE}/teams", params={"limit":32,"active":"true"})
            r.raise_for_status(); data = r.json()
    except Exception as e:
        logger.error("Teams list failed: %s", e); return {}
    ids = [_id_from_ref(i.get("$ref","")) for i in (data.get("items") or []) if _id_from_ref(i.get("$ref",""))]
    sem = asyncio.Semaphore(8)
    async def _one(tid):
        async with sem:
            try:
                async with httpx.AsyncClient(timeout=10.0) as c:
                    r = await c.get(f"{CORE_BASE}/teams/{tid}"); r.raise_for_status()
                    raw = r.json().get("abbreviation","").upper()
                    return tid, _REMAP.get(raw, raw)
            except: return tid, ""
    pairs = await asyncio.gather(*[_one(tid) for tid in ids])
    return {tid: abbr for tid, abbr in pairs if abbr}

def _build_game_record(event_id, game_time, home_abbr, away_abbr, odds_obj):
    ht = odds_obj.get("homeTeamOdds") or {}
    at = odds_obj.get("awayTeamOdds") or {}
    hs = _float(odds_obj.get("spread"))
    return {"source":odds_obj.get("_provider_name","draftkings"),"external_id":event_id,"espn_provider_id":odds_obj.get("_provider_id","100"),"home_team":home_abbr,"away_team":away_abbr,"game_time":game_time,"home_spread":hs,"away_spread":None if hs is None else round(-hs,1),"home_spread_juice":_american(ht.get("spreadOdds")),"away_spread_juice":_american(at.get("spreadOdds")),"home_ml":_american(ht.get("moneyLine")),"away_ml":_american(at.get("moneyLine")),"total":_float(odds_obj.get("overUnder")),"over_juice":_american(odds_obj.get("overOdds")),"under_juice":_american(odds_obj.get("underOdds"))}

def _pick_best_provider_odds(odds_list):
    pm = {}
    for odds in odds_list:
        p = odds.get("provider") or {}
        pid = str(p.get("id","")) if isinstance(p,dict) else ""
        if pid: pm[pid] = odds
    for pid, pname in PROVIDER_PRIORITY:
        if pid in pm:
            obj = dict(pm[pid]); obj["_provider_id"]=pid; obj["_provider_name"]=pname; return obj
    for odds in odds_list:
        if odds.get("spread") is not None or odds.get("overUnder") is not None:
            obj = dict(odds); p = odds.get("provider") or {}
            obj["_provider_id"] = str(p.get("id","unknown")) if isinstance(p,dict) else "unknown"
            obj["_provider_name"] = (p.get("name","unknown") if isinstance(p,dict) else "unknown").lower().replace(" ","_")
            return obj
    return None

def _id_from_ref(ref):
    import re as _re; m = _re.search(r"/teams/(\d+)", ref); return m.group(1) if m else ""

def _current_week(now=None):
    import math
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    return max(1, min(22, math.ceil(((now - datetime(now.year, 9, 7, tzinfo=timezone.utc)).days + 1) / 7)))

def _float(val):
    try: return float(val) if val is not None else None
    except: return None

def _american(val):
    if val is None: return None
    try: v = int(round(float(val))); return v if v != 0 else -110
    except: return None