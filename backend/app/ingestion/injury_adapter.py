"""
Injury Adapter â€“ ESPN Core API (sports.core.api.espn.com).
Fetches per-team injuries concurrently; follows $ref URLs for full records.
"""
from __future__ import annotations
import asyncio, logging, re
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
_REMAP = {"WSH":"WAS","JAX":"JAC","LVR":"LV"}
_KEY_POS = {"QB","RB","WR","TE","LT","LG","C","RG","RT","OT","OL","DE","DT","NT","EDGE","LB","MLB","ILB","OLB","CB","S","SS","FS"}

async def fetch_injuries() -> list[dict]:
    teams = await _get_teams()
    if not teams: logger.error("Could not fetch teams"); return []
    sem = asyncio.Semaphore(8)
    results = await asyncio.gather(*[_team_injuries(t, sem) for t in teams], return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, list): out.extend(r)
    logger.info("Injury adapter: %d records", len(out))
    return out

async def _get_teams():
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(f"{CORE}/teams", params={"limit":32,"active":"true"})
            r.raise_for_status(); data = r.json()
    except Exception as e:
        logger.error("Teams fetch failed: %s", e); return []
    teams = []
    for item in (data.get("items") or []):
        tid = item.get("id") or _id_from_ref(item.get("$ref",""))
        if not tid: continue
        teams.append({"id": tid, "abbreviation": (item.get("abbreviation") or "").upper()})
    return teams

async def _team_injuries(team: dict, sem: asyncio.Semaphore) -> list[dict]:
    tid, abbr = team["id"], team.get("abbreviation","")
    async with sem:
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.get(f"{CORE}/teams/{tid}/injuries", params={"limit":100})
                r.raise_for_status(); data = r.json()
        except Exception as e:
            logger.debug("Team %s injuries failed: %s", tid, e); return []
    items = data.get("items") or []
    if not items: return []
    if not abbr: abbr = await _resolve_abbr(tid)
    ref_sem = asyncio.Semaphore(5)
    records = await asyncio.gather(*[_injury_record(i, abbr, ref_sem) for i in items], return_exceptions=True)
    return [r for r in records if isinstance(r, dict)]

async def _injury_record(item: dict, abbr: str, sem: asyncio.Semaphore) -> Optional[dict]:
    if item.get("athlete") or item.get("status"):
        return _parse(item, abbr)
    ref = item.get("$ref","")
    if not ref: return None
    async with sem:
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(ref); r.raise_for_status(); record = r.json()
        except Exception: return None
    return _parse(record, abbr)

def _parse(rec: dict, abbr: str) -> Optional[dict]:
    athlete = rec.get("athlete") or {}
    name = athlete.get("fullName") or athlete.get("displayName") or (
        f"{athlete.get('firstName','')} {athlete.get('lastName','')}".strip()) or "Unknown"
    pos_obj = athlete.get("position") or {}
    pos = (pos_obj.get("abbreviation") or "").upper()
    status_obj = rec.get("status") or {}
    raw = status_obj.get("name") or status_obj.get("description") or rec.get("status") or ""
    if isinstance(raw, dict): raw = raw.get("name","")
    status = _norm(str(raw).split("(")[0].strip())
    if not status: return None
    type_obj = rec.get("type") or rec.get("injury",{}).get("type") or {}
    inj_type = (type_obj.get("description") or type_obj.get("name") or rec.get("longComment") or "")
    is_qb = pos == "QB"
    return {"team_abbreviation": _remap(abbr), "espn_athlete_id": str(athlete.get("id","")) or None,
        "athlete_name": name, "position": pos or None, "jersey_number": athlete.get("jersey") or None,
        "status": status, "injury_type": inj_type[:64] if inj_type else None,
        "is_qb": is_qb, "is_key_player": is_qb or pos in _KEY_POS,
        "reported_at": _dt(rec.get("date") or rec.get("reportedAt"))}

async def _resolve_abbr(tid):
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{CORE}/teams/{tid}"); r.raise_for_status()
            return _remap((r.json().get("abbreviation") or "").upper())
    except: return ""

def compute_injury_impact(home, away):
    net = _impact(away) - _impact(home)
    score = min(abs(net)/8.0*100, 100)
    notes = []
    for injuries, label in [(home,"home"),(away,"away")]:
        qb_out = next((i for i in injuries if i["is_qb"] and i["status"] in ("Out","Doubtful")), None)
        qb_q   = next((i for i in injuries if i["is_qb"] and i["status"]=="Questionable"), None)
        if qb_out: notes.append(f"?? {qb_out['athlete_name']} ({qb_out['status']}) â€“ {label} QB")
        elif qb_q: notes.append(f"?? {qb_q['athlete_name']} (Questionable) â€“ {label} QB watch")
        ko = sum(1 for i in injuries if i["is_key_player"] and i["status"] in ("Out","Doubtful"))
        if ko >= 2: notes.append(f"{label.capitalize()} missing {ko} key players")
    return round(score,1), notes

def _impact(injuries):
    w = {"Out":3.0,"Doubtful":2.0,"Questionable":1.0,"Probable":0.25,"IR":3.0,"PUP":2.5,"NFI":1.5}
    return sum(w.get(i.get("status",""),0)*(5 if i.get("is_qb") else 1 if i.get("is_key_player") else 0) for i in injuries)

def _id_from_ref(ref):
    m = re.search(r"/teams/(\d+)", ref); return m.group(1) if m else ""
def _norm(raw):
    return {"out":"Out","doubtful":"Doubtful","questionable":"Questionable","probable":"Probable",
        "injured reserve":"IR","ir":"IR","pup":"PUP","nfi":"NFI","day-to-day":"Questionable"}.get(raw.lower(), raw)
def _dt(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except: return None
def _remap(a): return _REMAP.get(a,a)



# Aliases for test compatibility
_normalise_status = _norm
_parse_date = _dt
_team_injury_impact = _impact
