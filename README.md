# 🏈 NFL Betting Edge

A private, invite-only web platform that aggregates NFL game odds, integrates real-time weather data, tracks sharp/public money splits, and surfaces systematic betting edges — powered by FastAPI, React, PostgreSQL, Redis, and Celery.

---

## Architecture Overview

```
nfl-edge/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   ├── core/             # Config, security, auth
│   │   ├── db/               # SQLAlchemy models + migrations
│   │   ├── ingestion/        # Scraper adapters (DraftKings, Kalshi, weather)
│   │   ├── tasks/            # Celery tasks
│   │   └── analysis/         # Edge detection logic
│   ├── tests/
│   ├── alembic/              # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 # React + Vite + TailwindCSS
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── api/
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   └── nginx/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
└── docs/
    ├── LOCAL_SETUP.md
    ├── CLOUD_DEPLOY.md
    └── INGESTION_ADAPTERS.md
```

---

## Quick Start (Local)

```bash
# 1. Clone and copy env
git clone https://github.com/you/nfl-edge.git && cd nfl-edge
cp .env.example .env        # fill in API keys

# 2. Spin up all services
docker compose -f infra/docker-compose.yml up --build

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Seed invite codes
docker compose exec backend python -m app.core.seed_invites

# 5. Open app
open http://localhost:3000
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.111, Python 3.12 |
| Task Queue | Celery 5.4 + Redis 7 |
| Database | PostgreSQL 16 + SQLAlchemy 2 |
| Caching | Redis 7 |
| Frontend | React 18 + Vite 5 + TailwindCSS 3 |
| Auth | JWT (invite-only registration) |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Cloud | Fly.io (backend) + Vercel (frontend) |

## Key Features

- **Live Odds Ingestion** — DraftKings spread/total/moneyline via adapter
- **Kalshi Market Data** — Event contract prices and volume
- **Weather Integration** — Open-Meteo API per stadium GPS coordinate
- **Sharp vs Public Split** — Public money %, bet count overlay
- **Edge Scoring** — Composite algorithm flagging games worth investigating
- **Invite-Only Auth** — Token-based invite registration
- **Auto-Refresh** — Celery beat polls data every 5 minutes during game week
