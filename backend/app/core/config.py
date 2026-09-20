from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "NFL Betting Edge"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str
    ASYNC_DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ── ESPN (no API key required) ────────────────────────────────────────────
    # Scoreboard — DraftKings odds via provider 1002
    ESPN_SCOREBOARD_URL: str = (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    )
    # Core API — per-event odds + line movement
    ESPN_CORE_URL: str = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
    # Preferred odds provider IDs (1002=DraftKings, 1004=ESPN BET fallback)
    ESPN_ODDS_PROVIDER_IDS: List[str] = ["1002", "1004"]

    # ── Action Network (no API key required) ──────────────────────────────────
    # Free public-money consensus data (bet %, money %, bet counts)
    AN_SCOREBOARD_URL: str = "https://api.actionnetwork.com/web/v1/scoreboard/nfl"
    AN_BOOK_ID: str = "15"  # 15 = DraftKings on Action Network

    # ── Public money scraper fallback (your own scraper) ─────────────────────
    SCRAPER_SOURCE: str = "file"         # "file" | "endpoint"
    SCRAPER_FILE_PATH: str = "/data/public_money.json"
    SCRAPER_ENDPOINT_URL: str = ""
    SCRAPER_API_KEY: str = ""

    # ── Open-Meteo weather (no API key required) ──────────────────────────────
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"

    # ── Auth ──────────────────────────────────────────────────────────────────
    INVITE_CODE_LENGTH: int = 16
    MAX_USERS: int = 20

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://nfl-edge.vercel.app",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
