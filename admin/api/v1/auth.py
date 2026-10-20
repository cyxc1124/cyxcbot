"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from nonebot_plugin_orm import get_session
from sqlalchemy import select, update

from admin.auth.jwt import create_access_token
from admin.auth.password import hash_password, verify_password
from admin.deps import CurrentUser, RequireSetup
from admin.schemas.common import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from shared.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, dependencies=[])
async def login(body: LoginRequest):
    async with get_session() as session:
        async with session.begin():
            user = await session.scalar(
                select(User).where(User.username == body.username)
            )
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
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

    token = create_access_token(
        username, {"uid": user_id, "is_admin": is_admin}, password_hash=password_hash
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse, dependencies=[RequireSetup])
async def me(user: CurrentUser):
    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.put("/password", response_model=TokenResponse, dependencies=[RequireSetup])
async def change_password(body: ChangePasswordRequest, user: CurrentUser):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    password_hash = hash_password(body.new_password)
    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                update(User)
                .where(User.id == user.id, User.password_hash == user.password_hash)
                .values(password_hash=password_hash)
            )
            if result.rowcount != 1:
                raise HTTPException(status_code=409, detail="密码已变更，请重新登录")

    token = create_access_token(
        user.username,
        {"uid": user.id, "is_admin": user.is_admin},
        password_hash=password_hash,
    )
    return TokenResponse(access_token=token)
