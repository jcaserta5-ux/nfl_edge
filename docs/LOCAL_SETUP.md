# Local Development Setup

## Prerequisites

| Tool | Min Version | Install |
|---|---|---|
| Docker Desktop | 4.30+ | https://docker.com |
| Git | 2.40+ | brew/apt/winget |
| Node.js | 20+ | https://nodejs.org |
| Python | 3.12+ | https://python.org |

---

## 1. Clone the Repository

```bash
git clone https://github.com/you/nfl-edge.git
cd nfl-edge
```

## 2. Configure Environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `SECRET_KEY` | Run: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ODDS_API_KEY` | https://the-odds-api.com — free tier works |
| `KALSHI_API_KEY` | https://kalshi.com → Account → API Keys |
| `SCRAPER_FILE_PATH` | Path to your scraper's JSON output (or leave default) |

## 3. Start All Services

```bash
cd infra
docker compose up --build
```

This starts: PostgreSQL, Redis, FastAPI backend, Celery worker, Celery beat, React frontend, Flower.

## 4. Run Database Migrations

```bash
docker compose exec backend alembic upgrade head
```

## 5. Seed Invite Codes

```bash
docker compose exec backend python -m app.core.seed_invites
```

Copy the printed codes and share them with friends.

## 6. Open the App

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| Flower (Celery monitor) | http://localhost:5555 |

---

## Connecting Your Scraper

### Option A — File drop (simplest)

Configure your existing scraper to write output to the shared Docker volume:
```
SCRAPER_FILE_PATH=/data/public_money.json
```
The Celery beat task `ingest_public_money` reads this file every 5 minutes.

### Option B — HTTP endpoint

Run your scraper as a service and point the adapter at it:
```
SCRAPER_SOURCE=endpoint
SCRAPER_ENDPOINT_URL=http://your-scraper:8001/games
SCRAPER_API_KEY=your-scraper-api-key
```

### Expected JSON format

```json
[
  {
    "home_team": "NE",
    "away_team": "BUF",
    "game_time": "2026-09-21T13:00:00",
    "home_spread_pct": 42.0,
    "away_spread_pct": 58.0,
    "over_pct": 63.0,
    "under_pct": 37.0,
    "home_money_pct": 35.0,
    "away_money_pct": 65.0,
    "total_bet_count": 14200
  }
]
```

Action Network exports are also supported — see `ingestion/public_money_adapter.py → parse_action_network_export()`.

---

## Common Commands

```bash
# View logs for specific service
docker compose logs -f backend

# Trigger an immediate odds ingest (without waiting for Celery)
docker compose exec backend python -c "
import asyncio
from app.ingestion.draftkings_adapter import fetch_dk_odds
print(asyncio.run(fetch_dk_odds()))
"

# Create a new DB migration
docker compose exec backend alembic revision --autogenerate -m "add_column_xyz"

# Run backend tests
docker compose exec backend pytest tests/ -v

# Reset everything (wipes DB)
docker compose down -v && docker compose up --build
```
