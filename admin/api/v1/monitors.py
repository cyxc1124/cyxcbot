"""Monitor status and manual check endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from admin.deps import AdminUser, RequireSetup
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

router = APIRouter(
    prefix="/monitors",
    tags=["monitors"],
    dependencies=[RequireSetup],
)


@router.get("/status", response_model=MonitorStatusResponse)
async def monitor_status(_: AdminUser):
    return MonitorStatusResponse(**get_monitor_status())


@router.get("/dynamic", response_model=DynamicMonitorStatusResponse)
async def dynamic_monitor_status(_: AdminUser):
    return DynamicMonitorStatusResponse(**build_dynamic_monitor_status())


@router.get("/live", response_model=LiveMonitorStatusResponse)
async def live_monitor_status(_: AdminUser):
    return LiveMonitorStatusResponse(**build_live_monitor_status())


@router.get("/system", response_model=SystemMonitorStatusResponse)
async def system_monitor_status(_: AdminUser):
    return SystemMonitorStatusResponse(**get_system_monitor_status())


@router.post("/dynamic/check", response_model=ManualCheckResponse)
async def manual_dynamic_check(_: AdminUser, uid: Optional[str] = None):
    result = await trigger_dynamic_check(uid)
    return ManualCheckResponse(**result)


@router.post("/live/check", response_model=ManualCheckResponse)
async def manual_live_check(_: AdminUser, room_id: Optional[str] = None):
    result = await trigger_live_check(room_id)
    return ManualCheckResponse(**result)
