"""
Auth routes: invite-based registration, login, token refresh.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_password, verify_password, create_access_token
from app.db.models import User, InviteCode
from app.db.session import get_db
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    invite_code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Validate invite code
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.code == body.invite_code,
            InviteCode.is_active == True,
            InviteCode.used_by == None,  # noqa: E711
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or already-used invite code")

    # Check if email/username already taken
    existing = await db.execute(
        select(User).where(
            (User.email == body.email) | (User.username == body.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email or username already registered")

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        invite_code_used=body.invite_code,
    )
    db.add(user)
    await db.flush()

    # Mark invite as used
    invite.used_by = user.id
    invite.used_at = datetime.utcnow()
    invite.is_active = False
    await db.commit()

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user.last_login = datetime.utcnow()
    await db.commit()
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)
