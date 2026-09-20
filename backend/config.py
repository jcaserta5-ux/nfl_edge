"""
Centralised settings — loaded once at startup via pydantic-settings.
All secrets come from environment variables (never hardcoded).
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "NFL Betting Edge"
    DEBUG: bool = False
    SECRET_KEY: str                          # REQUIRED
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str                        # REQUIRED  e.g. postgresql+asyncpg://...
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    CACHE_TTL_SECONDS: int = 300             # 5 min default

    # ── Celery ───────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ── External APIs ────────────────────────────────────────────────────
    ODDS_API_KEY: str = ""                   # The-Odds-API
    WEATHER_API_KEY: str = ""               # OpenWeatherMap
    DRAFTKINGS_BASE_URL: str = "https://sportsbook.draftkings.com"
    KALSHI_API_KEY: str = ""
    KALSHI_BASE_URL: str = "https://trading-api.kalshi.com/trade-api/v2"

    # ── Invite system ────────────────────────────────────────────────────
    INVITE_ONLY: bool = True
    MAX_USERS: int = 50
    ADMIN_EMAIL: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
