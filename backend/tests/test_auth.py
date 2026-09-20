"""Tests for invite-gated registration and JWT login."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_with_valid_invite(client: AsyncClient, invite):
    resp = await client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "password123",
        "invite_code": invite.code,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_with_invalid_invite(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "fail@example.com",
        "username": "failuser",
        "password": "password123",
        "invite_code": "NOTAVALIDCODE123",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_invite_can_only_be_used_once(client: AsyncClient, invite):
    payload = {
        "email": "first@example.com",
        "username": "firstuser",
        "password": "password123",
        "invite_code": invite.code,
    }
    resp1 = await client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 201

    payload["email"] = "second@example.com"
    payload["username"] = "seconduser"
    resp2 = await client.post("/api/auth/register", json=payload)
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, user):
    resp = await client.post(
        "/api/auth/login",
        data={"username": user.email, "password": "testpass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, user):
    resp = await client.post(
        "/api/auth/login",
        data={"username": user.email, "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient):
    resp = await client.get("/api/games/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(client: AsyncClient, auth_headers):
    resp = await client.get("/api/games/?season=2026&week=1", headers=auth_headers)
    assert resp.status_code == 200
    assert "games" in resp.json()
