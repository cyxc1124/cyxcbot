"""Audit log and system event endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from nonebot_plugin_orm import get_session

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.audit import AuditLogResponse, SystemEventResponse
from admin.schemas.common import PaginatedResponse
from shared.db.models import AuditLog, SystemEvent

router = APIRouter(
    tags=["audit"],
    dependencies=[RequireSetup],
)


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    session = get_session()
    async with session.begin():
        total = await session.scalar(select(func.count()).select_from(AuditLog)) or 0
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.scalars(stmt)).all()
        items = [AuditLogResponse.model_validate(r, from_attributes=True) for r in rows]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/events", response_model=PaginatedResponse[SystemEventResponse])
async def list_system_events(
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    session = get_session()
    async with session.begin():
        total = await session.scalar(select(func.count()).select_from(SystemEvent)) or 0
        stmt = (
            select(SystemEvent)
            .order_by(SystemEvent.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.scalars(stmt)).all()
        items = [SystemEventResponse.model_validate(r, from_attributes=True) for r in rows]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
