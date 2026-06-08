"""Monitor status and manual check endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.monitors import (
    DynamicMonitorStatusResponse,
    LiveMonitorStatusResponse,
    ManualCheckResponse,
    MonitorStatusResponse,
    SystemMonitorStatusResponse,
)
from admin.services.monitor_bridge import (
    build_dynamic_monitor_status,
    build_live_monitor_status,
    get_monitor_status,
    get_system_monitor_status,
    trigger_dynamic_check,
    trigger_live_check,
)
from shared.audit.service import write_audit
from shared.config.service import get_config_service
from shared.db.enums import AuditAction

router = APIRouter(
    prefix="/monitors",
    tags=["monitors"],
    dependencies=[RequireSetup],
)


@router.get("/status", response_model=MonitorStatusResponse)
async def monitor_status(_: CurrentUser):
    return MonitorStatusResponse(**get_monitor_status())


@router.get("/dynamic", response_model=DynamicMonitorStatusResponse)
async def dynamic_monitor_status(_: CurrentUser):
    return DynamicMonitorStatusResponse(**build_dynamic_monitor_status())


@router.get("/live", response_model=LiveMonitorStatusResponse)
async def live_monitor_status(_: CurrentUser):
    return LiveMonitorStatusResponse(**build_live_monitor_status())


@router.get("/system", response_model=SystemMonitorStatusResponse)
async def system_monitor_status(_: CurrentUser):
    return SystemMonitorStatusResponse(**get_system_monitor_status())


@router.post("/dynamic/check", response_model=ManualCheckResponse)
async def manual_dynamic_check(
    request: Request, user: CurrentUser, uid: Optional[str] = None
):
    result = await trigger_dynamic_check(uid)
    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.MONITOR_MANUAL_CHECK,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"type": "dynamic", "uid": uid}),
    )
    return ManualCheckResponse(**result)


@router.post("/live/check", response_model=ManualCheckResponse)
async def manual_live_check(
    request: Request, user: CurrentUser, room_id: Optional[str] = None
):
    result = await trigger_live_check(room_id)
    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.MONITOR_MANUAL_CHECK,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"type": "live", "room_id": room_id}),
    )
    return ManualCheckResponse(**result)
