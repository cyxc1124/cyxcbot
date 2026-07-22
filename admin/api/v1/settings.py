"""Settings endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from admin.deps import AdminUser, RequireSetup
from admin.schemas.settings import (
    CookieTestResultResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from admin.services.connection_status import (
    bilibili_status_message,
    get_bilibili_connection_status,
)
from shared.config.command_aliases import (
    merge_partial_command_aliases,
    normalize_command_aliases,
    normalize_extra_prefixes,
    serialize_command_aliases,
    validation_error,
)
from shared.config.message_templates import MESSAGE_TEMPLATE_KEYS
from shared.config.rust_rcon import command_aliases_rust_rcon_conflict
from shared.config.service import get_config_service

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[RequireSetup],
)


@router.get("", response_model=SettingsResponse)
async def get_settings(_: AdminUser):
    svc = get_config_service()
    data = svc.settings_for_api()
    return SettingsResponse(**data)


@router.patch("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdateRequest, _: AdminUser):
    svc = get_config_service()
    updates: dict[str, str] = {}

    if body.dynamic_monitor_interval is not None:
        updates["dynamic_monitor_interval"] = str(body.dynamic_monitor_interval)
    if body.dynamic_monitor_use_stagger is not None:
        updates["dynamic_monitor_use_stagger"] = str(
            body.dynamic_monitor_use_stagger
        ).lower()
    if body.dynamic_enable_screenshot is not None:
        updates["dynamic_enable_screenshot"] = str(
            body.dynamic_enable_screenshot
        ).lower()
    for key in MESSAGE_TEMPLATE_KEYS:
        value = getattr(body, key, None)
        if value is not None:
            updates[key] = value.strip()[:500]
    if body.live_monitor_interval is not None:
        updates["live_monitor_interval"] = str(body.live_monitor_interval)
    if body.live_monitor_include_info is not None:
        updates["live_monitor_include_info"] = str(
            body.live_monitor_include_info
        ).lower()
    if body.live_monitor_use_websocket is not None:
        updates["live_monitor_use_websocket"] = str(
            body.live_monitor_use_websocket
        ).lower()
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
    if body.command_aliases is not None:
        # 与当前快照合并后再 normalize：
        # 1) 只传部分命令时，未提及的命令保留原有配置（而非被
        #    normalize_command_aliases 的缺省填充逻辑重置为出厂默认）；
        # 2) 同一条命令内只传 enabled 或只传 triggers 时，用 exclude_unset
        #    只取客户端真正传入的字段与当前值合并，而不是用 Pydantic 为未传
        #    字段填的默认值（enabled=True/triggers=[]）整条覆盖，否则单独
        #    改开关会清空触发词、单独改触发词会误重启用。
        current = serialize_command_aliases(svc.get_snapshot().command_aliases)
        patch = {
            cid: entry.model_dump(exclude_unset=True)
            for cid, entry in body.command_aliases.items()
        }
        normalized = normalize_command_aliases(
            merge_partial_command_aliases(current, patch)
        )
        error = validation_error(normalized)
        if error:
            raise HTTPException(status_code=400, detail=error)
        rcon_conflict = command_aliases_rust_rcon_conflict(
            normalized, svc.get_snapshot().rust_rcon_bindings
        )
        if rcon_conflict:
            raise HTTPException(status_code=400, detail=rcon_conflict)
        updates["command_aliases"] = json.dumps(
            serialize_command_aliases(normalized), ensure_ascii=False
        )
    if body.command_extra_prefixes is not None:
        updates["command_extra_prefixes"] = json.dumps(
            normalize_extra_prefixes(body.command_extra_prefixes), ensure_ascii=False
        )

    if updates:
        await svc.set_settings(updates)
        await svc.reload()

    return SettingsResponse(**svc.settings_for_api())


@router.post("/test-cookie", response_model=CookieTestResultResponse)
async def test_cookie(_: AdminUser):
    status = await get_bilibili_connection_status()
    return CookieTestResultResponse(
        success=bool(status.get("logged_in")),
        message=bilibili_status_message(status),
        status=str(status.get("status") or ""),
        username=status.get("username"),
        uid=status.get("uid"),
    )
