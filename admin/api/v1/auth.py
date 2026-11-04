"""Authentication endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from nonebot_plugin_orm import get_session
from sqlalchemy import select, update

from admin.auth.jwt import create_access_token
from admin.auth.login_limiter import login_limiter
from admin.auth.password import hash_password, verify_password
from admin.auth.session import (
    SESSION_COOKIE,
    SESSION_COOKIE_PATH,
    auth_response,
    browser_session_requested,
    require_browser_session,
)
from admin.deps import CurrentUser, RequireSetup
from admin.schemas.common import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    TokenResponse,
    UserResponse,
)
from shared.db.models import User

# 用户不存在时也跑一次 bcrypt，避免响应时间暴露用户名是否存在。
_DUMMY_HASH = hash_password("cyxcbot-dummy-password")

router = APIRouter(
    prefix="/auth", tags=["auth"], dependencies=[Depends(browser_session_requested)]
)


@router.post("/login", response_model=TokenResponse | MessageResponse)
async def login(body: LoginRequest, request: Request):
    # 反向代理后 client.host 是代理地址；按用户名的限制仍然有效。
    ip = request.client.host if request.client else ""
    retry_after = login_limiter.retry_after(ip, body.username)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
            headers={"Retry-After": str(retry_after)},
        )

    async with get_session() as session:
        async with session.begin():
            user = await session.scalar(
                select(User).where(User.username == body.username)
            )
            # Read attributes inside session — lazy load fails after block exits
            password_hash = user.password_hash if user else _DUMMY_HASH
            user_id = user.id if user else None
            username = user.username if user else None
            is_admin = user.is_admin if user else False

    # bcrypt 约 0.2s，放到线程里避免阻塞事件循环（机器人消息处理与监控共用）。
    password_ok = await asyncio.to_thread(verify_password, body.password, password_hash)
    if not user_id or not password_ok:
        login_limiter.record_failure(ip, body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    login_limiter.record_success(body.username)

    token = create_access_token(
        username, {"uid": user_id, "is_admin": is_admin}, password_hash=password_hash
    )
    return auth_response(request, token)


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request):
    require_browser_session(request)
    response = JSONResponse(
        {"message": "Logged out"}, headers={"Cache-Control": "no-store"}
    )
    response.delete_cookie(
        SESSION_COOKIE, path=SESSION_COOKIE_PATH, httponly=True, samesite="strict"
    )
    return response


@router.get("/me", response_model=UserResponse, dependencies=[RequireSetup])
async def me(user: CurrentUser):
    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.put(
    "/password",
    response_model=TokenResponse | MessageResponse,
    dependencies=[RequireSetup],
)
async def change_password(
    body: ChangePasswordRequest, user: CurrentUser, request: Request
):
    if not await asyncio.to_thread(
        verify_password, body.current_password, user.password_hash
    ):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if await asyncio.to_thread(verify_password, body.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    password_hash = await asyncio.to_thread(hash_password, body.new_password)
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
    return auth_response(request, token)
