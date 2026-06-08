"""Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.settings import SettingsResponse, SettingsUpdateRequest
from admin.services.monitor_bridge import reload_all_monitors
from shared.audit.service import write_audit
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType
from shared.audit.service import write_system_event
from shared.security.crypto import encrypt_value

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

    if body.clear_bilibili_cookie:
        updates["bilibili_cookie_encrypted"] = ""
    elif body.bilibili_cookie is not None and body.bilibili_cookie.strip():
        updates["bilibili_cookie_encrypted"] = encrypt_value(body.bilibili_cookie.strip())

    if updates:
        await svc.set_settings(updates)
        await svc.reload()
        await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details({k: "***" if "cookie" in k else v for k, v in updates.items()}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Settings updated via Web Admin")

    return SettingsResponse(**svc.settings_for_api())
