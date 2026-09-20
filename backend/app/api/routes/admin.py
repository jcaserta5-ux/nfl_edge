"""
Admin routes — invite code management (generate, list, revoke).
All endpoints require is_admin=True.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_admin_user
from app.db.models import InviteCode, User

router = APIRouter(prefix="/admin", tags=["admin"])

CODE_CHARS = string.ascii_letters + string.digits


def _gen_code(length: int = 16) -> str:
    return "".join(secrets.choice(CODE_CHARS) for _ in range(length))


# ── Invite codes ──────────────────────────────────────────────────────────────

class GenerateInvitesRequest(BaseModel):
    count: int = 5
    expires_at: Optional[datetime] = None


@router.post("/invites/generate")
async def generate_invites(
    body: GenerateInvitesRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    if body.count < 1 or body.count > 50:
        raise HTTPException(400, "count must be 1–50")

    codes = []
    for _ in range(body.count):
        invite = InviteCode(
            code=_gen_code(),
            created_by=admin.id,
            is_active=True,
            expires_at=body.expires_at,
        )
        db.add(invite)
        codes.append(invite)

    await db.commit()
    for c in codes:
        await db.refresh(c)

    return {"generated": [_serialize_invite(c) for c in codes]}


@router.get("/invites")
async def list_invites(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_admin_user),
):
    result = await db.execute(
        select(InviteCode).order_by(InviteCode.created_at.desc())
    )
    invites = result.scalars().all()
    return {"invites": [_serialize_invite(i) for i in invites]}


@router.delete("/invites/{code}")
async def revoke_invite(
    code: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_admin_user),
):
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == code)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(404, "Invite code not found")
    invite.is_active = False
    await db.commit()
    return {"revoked": code}


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_admin_user),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return {"users": [_serialize_user(u) for u in users]}


@router.patch("/users/{user_id}/admin")
async def toggle_admin(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    if user_id == admin.id:
        raise HTTPException(400, "Cannot change your own admin status")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_admin = not user.is_admin
    await db.commit()
    return {"user_id": user_id, "is_admin": user.is_admin}


# ── Serializers ───────────────────────────────────────────────────────────────

def _serialize_invite(i: InviteCode) -> dict:
    return {
        "code":       i.code,
        "is_active":  i.is_active,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "expires_at": i.expires_at.isoformat() if i.expires_at else None,
        "used_at":    i.used_at.isoformat() if i.used_at else None,
        "used_by":    i.used_by,
    }


def _serialize_user(u: User) -> dict:
    return {
        "id":         u.id,
        "email":      u.email,
        "username":   u.username,
        "is_admin":   u.is_admin,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
    }
