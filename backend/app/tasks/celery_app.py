"""
Celery application + beat schedule for periodic NFL data ingestion.

Data sources (all free, no API keys required):
  - ESPN Scoreboard API   → DraftKings spread / ML / total lines
  - ESPN Core API         → per-game line movement history
  - Action Network API    → public betting %, money %, bet counts
  - Open-Meteo API        → per-stadium weather forecasts
  - ESPN FPI / Standings  → power rankings (new)
  - ESPN Injuries API     → player injury designations (new)

Kalshi integration is deferred — not included in this schedule.
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "nfl_edge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.ingest_odds",              # ESPN → DraftKings lines
        "app.tasks.ingest_public_money",      # Action Network → bet/money %
        "app.tasks.ingest_weather",           # Open-Meteo → stadium weather
        "app.tasks.ingest_power_rankings",    # ESPN FPI → power rankings (NEW)
        "app.tasks.ingest_injuries",          # ESPN Injuries → injury reports (NEW)
        "app.tasks.run_analysis",             # Edge engine composite score
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/New_York",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ── Beat schedule ─────────────────────────────────────────────────────────────
#
# ESPN scoreboard is polled frequently because DK lines move in-week.
# Action Network is polled at the same cadence — very lenient on rate limits.
# Weather is 30-min because forecasts don't change faster than that.
# Power rankings update once a day (ESPN FPI publishes weekly on Tuesdays).
# Injuries update every 3 hours — major changes on Wed/Thu/Fri practice reports.
# Edge analysis runs after each odds + money cycle.
# Daily 6am ET refresh ensures we catch any new games added to the schedule.
#
celery_app.conf.beat_schedule = {
    # ── Odds (ESPN → DraftKings) ──────────────────────────────────────────────
    "ingest-espn-odds-every-5min": {
        "task": "app.tasks.ingest_odds.run_odds_ingestion",
        "schedule": 300,    # every 5 minutes
        "kwargs": {},
    },
    # ── Public money (Action Network) ─────────────────────────────────────────
    "ingest-public-money-every-5min": {
        "task": "app.tasks.ingest_public_money.run_public_money_ingestion",
        "schedule": 300,
    },
    # ── Weather (Open-Meteo) ──────────────────────────────────────────────────
    "ingest-weather-every-30min": {
        "task": "app.tasks.ingest_weather.run_weather_ingestion",
        "schedule": 1800,   # every 30 minutes
    },
    # ── Power rankings (ESPN FPI) — daily at 3 AM ET ──────────────────────────
    "ingest-power-rankings-daily": {
        "task": "app.tasks.ingest_power_rankings.run_power_rankings_ingestion",
        "schedule": crontab(hour=3, minute=0),   # 3 AM ET daily
    },
    # ── Power rankings mid-week refresh (Tuesday when ESPN publishes FPI) ──────
    "ingest-power-rankings-tuesday": {
        "task": "app.tasks.ingest_power_rankings.run_power_rankings_ingestion",
        "schedule": crontab(hour=10, minute=0, day_of_week=2),  # Tuesday 10 AM ET
    },
    # ── Injuries — every 3 hours ──────────────────────────────────────────────
    "ingest-injuries-every-3h": {
        "task": "app.tasks.ingest_injuries.run_injury_ingestion",
        "schedule": 10800,  # every 3 hours
    },
    # ── Edge analysis ─────────────────────────────────────────────────────────
    "run-edge-analysis-every-10min": {
        "task": "app.tasks.run_analysis.run_edge_analysis",
        "schedule": 600,    # every 10 minutes
    },
    # ── Daily full refresh (catches new games added to the schedule) ───────────
    "daily-full-refresh": {
        "task": "app.tasks.ingest_odds.run_odds_ingestion",
        "schedule": crontab(hour=6, minute=0),  # 6 AM ET
    },
}
