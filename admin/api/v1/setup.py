"""Setup flow endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from nonebot_plugin_orm import get_session
from sqlalchemy import func, select

from admin.auth.jwt import create_access_token
from admin.auth.password import hash_password
from admin.auth.session import auth_response, browser_session_requested
from admin.schemas.common import (
    MessageResponse,
    SetupRequest,
    SetupStatusResponse,
    TokenResponse,
)
from admin.services.setup_guard import claim_initial_setup
from shared.db.models import User

router = APIRouter(
    prefix="/setup", tags=["setup"], dependencies=[Depends(browser_session_requested)]
)


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status():
    async with get_session() as session:
        async with session.begin():
            count = await session.scalar(select(func.count()).select_from(User)) or 0
    return SetupStatusResponse(initialized=count > 0, user_count=count)


@router.post("", response_model=TokenResponse | MessageResponse)
async def setup(body: SetupRequest, request: Request):
    async with get_session() as session:
        async with session.begin():
            await claim_initial_setup(session)

            password_hash = hash_password(body.password)
            user = User(
                username=body.username,
                password_hash=password_hash,
                is_admin=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            username = user.username
            is_admin = user.is_admin

    token = create_access_token(
        username, {"uid": user_id, "is_admin": is_admin}, password_hash=password_hash
    )
    return auth_response(request, token)
