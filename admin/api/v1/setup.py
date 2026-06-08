"""Setup flow endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from nonebot_plugin_orm import get_session

from admin.auth.jwt import create_access_token
from admin.auth.password import hash_password
from admin.schemas.common import SetupRequest, SetupStatusResponse, TokenResponse
from shared.audit.service import write_audit, write_system_event
from shared.db.enums import AuditAction, SystemEventType
from shared.db.models import User

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status():
    session = get_session()
    async with session.begin():
        count = await session.scalar(select(func.count()).select_from(User)) or 0
    return SetupStatusResponse(initialized=count > 0, user_count=count)


@router.post("", response_model=TokenResponse)
async def setup(request: Request, body: SetupRequest):
    session = get_session()
    async with session.begin():
        count = await session.scalar(select(func.count()).select_from(User)) or 0
        if count > 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup already completed")

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

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETUP,
        actor_user_id=user_id,
        actor_username=username,
        ip_address=ip,
        details=f'{{"username": "{username}"}}',
    )
    await write_system_event(
        SystemEventType.SETUP_COMPLETE,
        f"Initial admin user '{username}' created",
    )

    token = create_access_token(username, {"uid": user_id, "is_admin": is_admin})
    return TokenResponse(access_token=token)
