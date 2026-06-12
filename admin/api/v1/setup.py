"""Setup flow endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from nonebot_plugin_orm import get_session
from sqlalchemy import func, select

from admin.auth.jwt import create_access_token
from admin.auth.password import hash_password
from admin.schemas.common import SetupRequest, SetupStatusResponse, TokenResponse
from admin.services.setup_guard import claim_initial_setup
from shared.db.models import User

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status():
    session = get_session()
    async with session.begin():
        count = await session.scalar(select(func.count()).select_from(User)) or 0
    return SetupStatusResponse(initialized=count > 0, user_count=count)


@router.post("", response_model=TokenResponse)
async def setup(body: SetupRequest):
    session = get_session()
    async with session.begin():
        await claim_initial_setup(session)

        user = User(
            username=body.username,
            password_hash=hash_password(body.password),
            is_admin=True,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        username = user.username
        is_admin = user.is_admin

    token = create_access_token(username, {"uid": user_id, "is_admin": is_admin})
    return TokenResponse(access_token=token)
