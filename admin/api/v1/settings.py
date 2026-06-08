"""Settings endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.settings import CookieTestResultResponse, SettingsResponse, SettingsUpdateRequest
from admin.services.connection_status import bilibili_status_message, get_bilibili_connection_status
from admin.services.monitor_bridge import reload_all_monitors
from shared.audit.service import write_audit, write_system_event
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[RequireSetup],
)


@router.get("", response_model=SettingsResponse)
async def get_settings(_: CurrentUser):
    svc = get_config_service()
    data = svc.settings_for_api()
    return SettingsResponse(**data)


@router.patch("", response_model=SettingsResponse)
async def update_settings(request: Request, body: SettingsUpdateRequest, user: CurrentUser):
    svc = get_config_service()
    updates: dict[str, str] = {}

    if body.dynamic_monitor_interval is not None:
        updates["dynamic_monitor_interval"] = str(body.dynamic_monitor_interval)
    if body.dynamic_enable_screenshot is not None:
        updates["dynamic_enable_screenshot"] = str(body.dynamic_enable_screenshot).lower()
    if body.live_monitor_interval is not None:
        updates["live_monitor_interval"] = str(body.live_monitor_interval)
    if body.live_monitor_include_info is not None:
        updates["live_monitor_include_info"] = str(body.live_monitor_include_info).lower()
    if body.live_monitor_use_websocket is not None:
        updates["live_monitor_use_websocket"] = str(body.live_monitor_use_websocket).lower()
    if body.audit_log_retention_days is not None:
        updates["audit_log_retention_days"] = str(body.audit_log_retention_days)
    if body.event_retention_days is not None:
        updates["event_retention_days"] = str(body.event_retention_days)
    if body.status_check_allowed_qq is not None:
        cleaned = [
            item.strip()
            for qq in body.status_check_allowed_qq
            for item in [str(qq).strip()]
            if item.isdigit()
        ]
        updates["status_check_allowed_qq"] = json.dumps(cleaned, ensure_ascii=False)
    if body.nonebot_superusers is not None:
        cleaned = [
            item.strip()
            for qq in body.nonebot_superusers
            for item in [str(qq).strip()]
            if item.isdigit()
        ]
        updates["nonebot_superusers"] = json.dumps(cleaned, ensure_ascii=False)

    if updates:
        await svc.set_settings(updates)
        await svc.reload()
        if any(k not in ("status_check_allowed_qq", "nonebot_superusers") for k in updates):
            await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details(updates),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Settings updated via Web Admin")

    return SettingsResponse(**svc.settings_for_api())


@router.post("/test-cookie", response_model=CookieTestResultResponse)
async def test_cookie(_: CurrentUser):
    status = await get_bilibili_connection_status()
    return CookieTestResultResponse(
        success=bool(status.get("logged_in")),
        message=bilibili_status_message(status),
        status=str(status.get("status") or ""),
        username=status.get("username"),
        uid=status.get("uid"),
    )
