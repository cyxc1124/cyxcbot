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
from shared.config.rust_rcon_custom import command_aliases_custom_command_conflict
from shared.config.service import get_config_service
from shared.security.crypto import encrypt_value

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
    if body.x_monitor_interval is not None:
        updates["x_monitor_interval"] = str(body.x_monitor_interval)
    if body.x_monitor_use_stagger is not None:
        updates["x_monitor_use_stagger"] = str(body.x_monitor_use_stagger).lower()
    if body.x_api_bearer is not None:
        bearer = body.x_api_bearer.strip()
        updates["x_api_bearer_encrypted"] = encrypt_value(bearer) if bearer else ""
    if body.x_proxy_enabled is not None:
        updates["x_proxy_enabled"] = str(body.x_proxy_enabled).lower()
    if body.x_proxy_scheme is not None:
        scheme = body.x_proxy_scheme.strip().lower()
        if scheme not in ("http", "https", "socks5"):
            raise HTTPException(status_code=400, detail="代理协议仅支持 http/https/socks5")
        updates["x_proxy_scheme"] = scheme
    if body.x_proxy_host is not None:
        updates["x_proxy_host"] = body.x_proxy_host.strip()
    if body.x_proxy_port is not None:
        updates["x_proxy_port"] = str(body.x_proxy_port)
    if body.x_proxy_username is not None:
        updates["x_proxy_username"] = body.x_proxy_username.strip()
    if body.x_proxy_password is not None:
        password = body.x_proxy_password
        updates["x_proxy_password_encrypted"] = (
            encrypt_value(password) if password else ""
        )
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
        snap = svc.get_snapshot()
        rcon_conflict = command_aliases_rust_rcon_conflict(
            normalized, snap.rust_rcon_bindings
        )
        if rcon_conflict:
            raise HTTPException(status_code=400, detail=rcon_conflict)
        custom_conflict = command_aliases_custom_command_conflict(
            normalized, snap.rust_rcon_custom_commands
        )
        if custom_conflict:
            raise HTTPException(status_code=400, detail=custom_conflict)
        updates["command_aliases"] = json.dumps(
            serialize_command_aliases(normalized), ensure_ascii=False
        )
    if body.command_extra_prefixes is not None:
        updates["command_extra_prefixes"] = json.dumps(
            normalize_extra_prefixes(body.command_extra_prefixes), ensure_ascii=False
        )
    if body.link_parser_shared_media_dir is not None:
        raw = body.link_parser_shared_media_dir.strip()
        if "\x00" in raw:
            raise HTTPException(status_code=400, detail="共享媒体目录路径无效")
        updates["link_parser_shared_media_dir"] = raw

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
