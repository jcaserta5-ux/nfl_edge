"""
NFL Betting Edge — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.config import settings
from backend.database import engine, Base
from backend.routers import auth, games, lines, weather, analysis, admin, invites
from backend.cache import init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_redis()
    yield
    # Shutdown (nothing needed; connection pools handle cleanup)


app = FastAPI(
    title="NFL Betting Edge API",
    version="1.0.0",
    description="Real-time NFL game analysis with betting line integration",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["auth"])
app.include_router(games.router,    prefix="/api/games",    tags=["games"])
app.include_router(lines.router,    prefix="/api/lines",    tags=["lines"])
app.include_router(weather.router,  prefix="/api/weather",  tags=["weather"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(admin.router,    prefix="/api/admin",    tags=["admin"])
app.include_router(invites.router,  prefix="/api/invites",  tags=["invites"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
