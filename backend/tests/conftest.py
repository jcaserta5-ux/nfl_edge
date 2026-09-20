"""
Pytest fixtures for NFL Edge backend tests.
Uses an in-memory SQLite database (via aiosqlite) so tests never need
a real Postgres or Redis instance.
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.models import Base
from app.db.session import get_db
from app.core.security import hash_password, create_access_token
from app.db.models import User, InviteCode, NFLTeam

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ── DB fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(db_engine):
    session_factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db):
    """FastAPI test client with DB dependency overridden."""
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ── Seed fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def invite(db) -> InviteCode:
    code = InviteCode(code="TESTINVITE123456", is_active=True)
    db.add(code)
    await db.commit()
    await db.refresh(code)
    return code


@pytest_asyncio.fixture
async def user(db, invite) -> User:
    u = User(
        email="testuser@example.com",
        username="testuser",
        hashed_password=hash_password("testpass123"),
        invite_code_used=invite.code,
    )
    db.add(u)
    invite.used_by = None  # will be set after flush
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def admin_user(db) -> User:
    u = User(
        email="admin@example.com",
        username="adminuser",
        hashed_password=hash_password("adminpass123"),
        is_admin=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def auth_headers(user) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(admin_user) -> dict:
    token = create_access_token(subject=str(admin_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def nfl_teams(db) -> list[NFLTeam]:
    teams = [
        NFLTeam(abbreviation="NE",  name="Patriots",  city="New England",  stadium_lat=42.09, stadium_lon=-71.26, is_dome=False),
        NFLTeam(abbreviation="BUF", name="Bills",     city="Buffalo",      stadium_lat=42.77, stadium_lon=-78.78, is_dome=False),
        NFLTeam(abbreviation="MIA", name="Dolphins",  city="Miami",        stadium_lat=25.96, stadium_lon=-80.24, is_dome=False),
        NFLTeam(abbreviation="LV",  name="Raiders",   city="Las Vegas",    stadium_lat=36.09, stadium_lon=-115.18, is_dome=True),
    ]
    for t in teams:
        db.add(t)
    await db.commit()
    return teams
