"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from admin.auth.jwt import create_access_token
from admin.auth.password import verify_password
from admin.deps import CurrentUser, RequireSetup
from admin.schemas.common import LoginRequest, TokenResponse, UserResponse
from shared.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, dependencies=[])
async def login(body: LoginRequest):
    session = get_session()
    async with session.begin():
        user = await session.scalar(select(User).where(User.username == body.username))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        # Read attributes inside session — lazy load fails after block exits
        password_hash = user.password_hash
        user_id = user.id
        username = user.username
        is_admin = user.is_admin

    if not verify_password(body.password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    token = create_access_token(username, {"uid": user_id, "is_admin": is_admin})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse, dependencies=[RequireSetup])
async def me(user: CurrentUser):
    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )
