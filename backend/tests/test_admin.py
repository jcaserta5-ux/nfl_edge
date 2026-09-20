"""Tests for admin invite management endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_generate_invites_as_admin(client: AsyncClient, admin_headers):
    resp = await client.post(
        "/api/admin/invites/generate",
        json={"count": 3},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["generated"]) == 3
    for inv in data["generated"]:
        assert len(inv["code"]) == 16
        assert inv["is_active"] is True


@pytest.mark.asyncio
async def test_generate_invites_non_admin_forbidden(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/admin/invites/generate",
        json={"count": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_invites(client: AsyncClient, admin_headers, invite):
    resp = await client.get("/api/admin/invites", headers=admin_headers)
    assert resp.status_code == 200
    codes = [i["code"] for i in resp.json()["invites"]]
    assert invite.code in codes


@pytest.mark.asyncio
async def test_revoke_invite(client: AsyncClient, admin_headers, invite):
    resp = await client.delete(
        f"/api/admin/invites/{invite.code}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["revoked"] == invite.code


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, admin_headers, user):
    resp = await client.get("/api/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()["users"]]
    assert user.email in emails
