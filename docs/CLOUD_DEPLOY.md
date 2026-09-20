# Cloud Deployment Guide

## Architecture: Fly.io (Backend) + Vercel (Frontend)

This is the recommended free/low-cost setup for a private friend group.

---

## Backend → Fly.io

### 1. Install Fly CLI
```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### 2. Create the app
```bash
cd backend
fly launch --name nfl-edge-api --region bos --no-deploy
```

### 3. Create managed Postgres
```bash
fly postgres create --name nfl-edge-db --region bos --vm-size shared-cpu-1x --volume-size 3
fly postgres attach nfl-edge-db --app nfl-edge-api
```

### 4. Create managed Redis (Upstash via Fly extension)
```bash
fly ext redis create --name nfl-edge-redis
```

### 5. Set secrets
```bash
fly secrets set \
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  ODDS_API_KEY="your-key" \
  KALSHI_API_KEY="your-key" \
  --app nfl-edge-api
```

### 6. Deploy
```bash
fly deploy --app nfl-edge-api
```

### 7. Run migrations + seed invites
```bash
fly ssh console --app nfl-edge-api -C "alembic upgrade head"
fly ssh console --app nfl-edge-api -C "python -m app.core.seed_invites"
```

### fly.toml (auto-generated, customize as needed)
```toml
app = "nfl-edge-api"
primary_region = "bos"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

---

## Celery Worker → Fly.io (separate process)

Add to `fly.toml`:
```toml
[[processes]]
  name = "worker"
  cmd = "celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2"

[[processes]]
  name = "beat"
  cmd = "celery -A app.tasks.celery_app beat --loglevel=info"
```

---

## Frontend → Vercel

### 1. Push frontend to GitHub
```bash
git subtree push --prefix frontend origin frontend-deploy
```
Or connect your full monorepo — Vercel auto-detects Vite.

### 2. Import on Vercel
1. Go to https://vercel.com/new
2. Import your GitHub repo
3. Set **Root Directory** → `frontend`
4. Set **Build Command** → `npm run build`
5. Set **Output Directory** → `dist`

### 3. Set environment variable
```
VITE_API_BASE_URL = https://nfl-edge-api.fly.dev/api
```

### 4. Deploy — done ✅

---

## Cost Estimate (friend group of ~10)

| Service | Tier | Monthly Cost |
|---|---|---|
| Fly.io backend | shared-cpu-1x, 512MB | ~$0–5 |
| Fly.io Postgres | 3GB volume | ~$0 (free allowance) |
| Upstash Redis | 10K cmd/day free | $0 |
| Vercel frontend | Hobby | $0 |
| **Total** | | **~$0–5/mo** |
