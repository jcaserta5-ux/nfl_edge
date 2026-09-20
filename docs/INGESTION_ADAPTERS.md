# Ingestion Adapters Reference

## Overview

NFL Edge uses four ingestion adapters that run as Celery tasks on a schedule.
**All four data sources are free and require no API keys.**

| Adapter | File | Schedule | Data Source | Key Required? |
|---|---|---|---|---|
| ESPN Odds | `espn_adapter.py` | Every 5 min | ESPN public API (DK lines via provider 1002) | ❌ None |
| Action Network | `public_money_adapter.py` | Every 5 min | Action Network public API | ❌ None |
| Open-Meteo Weather | `weather_adapter.py` | Every 30 min | Open-Meteo forecast API | ❌ None |
| Edge Analysis | `analysis/edge_engine.py` | Every 10 min | Runs on persisted data | — |

> **Kalshi integration** is deferred. The adapter stub (`kalshi_adapter.py`) is kept for future reference.
> **DraftKings direct API** is deprecated — DK lines are now sourced through ESPN, which surfaces the same numbers.

---

## ESPN Odds Adapter

**File:** `backend/app/ingestion/espn_adapter.py`
**No API key required.**

Pulls DraftKings spread, moneyline, and total lines from ESPN's undocumented
public scoreboard API. ESPN embeds odds from multiple sportsbooks — we use
**provider ID 1002 (DraftKings)** as primary and **1004 (ESPN BET)** as fallback.

### Endpoints Used

| Endpoint | Purpose |
|---|---|
| `site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard` | All games + embedded odds for the week |
| `sports.core.api.espn.com/v2/.../events/{id}/competitions/{id}/odds` | Per-event detailed odds (used when scoreboard odds missing) |
| `sports.core.api.espn.com/v2/.../events/{id}/competitions/{id}/odds/{provider_id}/history/0/movement` | Line movement history |

### ESPN Scoreboard Odds Response Shape

```json
{
  "provider": { "id": "1002", "name": "DraftKings" },
  "details": "NE -3.5",
  "overUnder": 44.5,
  "spread": -3.5,
  "overOdds": -110,
  "underOdds": -110,
  "homeTeamOdds": { "moneyLine": -165, "spreadOdds": -110, "favorite": true },
  "awayTeamOdds": { "moneyLine": 145,  "spreadOdds": -110, "favorite": false }
}
```

> **Note:** ESPN's `spread` field is the **home team spread** (negative = home favorite). The away spread is computed as `-spread`.

### Usage

```python
import asyncio
from app.ingestion.espn_adapter import fetch_espn_scoreboard_odds, fetch_espn_line_movement

# Get all games for Week 3 of 2026
games = asyncio.run(fetch_espn_scoreboard_odds(season=2026, week=3))

# Get line movement history for a specific ESPN event ID
movements = asyncio.run(fetch_espn_line_movement(event_id="401547417"))
```

### Output Fields per Game

```python
{
    "source": "draftkings",        # or "espn_bet" if DK not available
    "external_id": "401547417",    # ESPN event ID
    "espn_provider_id": "1002",
    "home_team": "NE",
    "away_team": "BUF",
    "game_time": "2026-09-21T17:00Z",
    "home_spread": -3.5,
    "away_spread": 3.5,
    "home_spread_juice": -110,
    "away_spread_juice": -110,
    "home_ml": -165,
    "away_ml": 145,
    "total": 44.5,
    "over_juice": -110,
    "under_juice": -110,
}
```

---

## Action Network Public Money Adapter

**File:** `backend/app/ingestion/public_money_adapter.py`
**No API key required.**

Fetches public betting consensus from Action Network's free undocumented API:
bet percentages, money percentages, and bet counts per game per market.

### Endpoint Used

```
GET https://api.actionnetwork.com/web/v1/scoreboard/nfl
    ?period=game&bookIds=15
```

`bookIds=15` scopes consensus to DraftKings on Action Network.

### Action Network Response Fields

| Our Field | AN Source Field |
|---|---|
| `home_spread_pct` | `consensus[type=spread].home_percent` |
| `away_spread_pct` | `consensus[type=spread].away_percent` |
| `home_money_pct` | `consensus[type=spread].home_money` |
| `away_money_pct` | `consensus[type=spread].away_money` |
| `over_pct` | `consensus[type=total].home_percent` |
| `under_pct` | `consensus[type=total].away_percent` |
| `home_ml_pct` | `consensus[type=moneyline].home_percent` |
| `away_ml_pct` | `consensus[type=moneyline].away_percent` |
| `total_bet_count` | `consensus[type=spread].bet_count` |

> Action Network uses `home/away` for over/under in the total market — `home = over`, `away = under`.
> Missing complement percentages are auto-derived: if `home_pct=42` and `away_pct` is missing, `away_pct=58` is computed.

### Usage

```python
import asyncio
from app.ingestion.public_money_adapter import fetch_action_network

records = asyncio.run(fetch_action_network())
# Returns list of dicts with home/away spread %, money %, over/under %, bet count
```

### Scraper Fallback

If Action Network is unavailable, the adapter falls back to your own scraper:

```bash
# .env settings for fallback
SCRAPER_SOURCE=file                      # or "endpoint"
SCRAPER_FILE_PATH=/data/public_money.json
```

Expected JSON format (same as Action Network output shape):
```json
[{
  "home_team": "NE", "away_team": "BUF",
  "game_time": "2026-09-21T17:00:00",
  "home_spread_pct": 42.0, "away_spread_pct": 58.0,
  "over_pct": 63.0, "under_pct": 37.0,
  "home_money_pct": 35.0, "away_money_pct": 65.0,
  "total_bet_count": 14200
}]
```

---

## Weather Adapter

**File:** `backend/app/ingestion/weather_adapter.py`
**No API key required.**

Uses Open-Meteo's free forecast API. Covers all 32 NFL stadiums.
Dome games (LV, ARI, MIN, DET, ATL, NO, DAL, HOU, IND) return neutral indoor defaults.

```python
import asyncio
from datetime import datetime
from app.ingestion.weather_adapter import fetch_game_weather

wx = asyncio.run(fetch_game_weather("BUF", datetime(2026, 9, 21, 13, 0)))
# { "temp_f": 48.0, "wind_mph": 18.0, "is_dome": False, ... }
```

**Weather impact thresholds in edge engine:**

| Condition | Threshold | Edge Signal |
|---|---|---|
| Wind | > 15 mph | Mild under lean |
| Wind | > 25 mph | Strong under lean |
| Snow | Any accumulation | Strong under lean |
| Temperature | < 25°F | Moderate under lean |

---

## Edge Engine

**File:** `backend/app/analysis/edge_engine.py`

Combines all ingested signals into a 0–100 composite score per game.

```python
from app.analysis.edge_engine import calculate_edge, GameSnapshot

snap = GameSnapshot(
    game_id=1, home_team="BUF", away_team="NE",
    home_spread=-7.0, home_spread_open=-5.5,   # 1.5pt line move
    home_spread_pct=68.0, home_money_pct=44.0, # sharp fade signal
    wind_mph=22.0, temp_f=28.0,                # weather
)
result = calculate_edge(snap)
# EdgeResult(composite_score=74.3, confidence='high', recommendation='away_spread')
```

**Score components and weights:**

| Component | Weight | Signal Source |
|---|---|---|
| Line Movement | 25% | ESPN line movement history |
| Sharp Money | 30% | Action Network money % vs bet % |
| Weather Impact | 15% | Open-Meteo wind/cold/precip |
| Kalshi Divergence | 15% | **Deferred** — scores as 0 until enabled |
| Public Fade | 15% | Action Network bet % concentration |
