"""Bilibili login endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.bilibili import (
    LogoutResponse,
    QrcodeLoginResponse,
    QrcodePollRequest,
    QrcodeStartResponse,
)
from admin.services.connection_status import bilibili_status_message, get_bilibili_connection_status
from admin.services.monitor_bridge import reload_all_monitors
from shared.audit.service import write_audit, write_system_event
from shared.bilibili.qrcode_login import (
    BilibiliQrcodeError,
    cookie_info_to_header,
    get_tv_qrcode,
    poll_tv_qrcode_login,
)
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType
from shared.security.crypto import encrypt_value

router = APIRouter(
    prefix="/bilibili",
    tags=["bilibili"],
    dependencies=[RequireSetup],
)


@router.get("/login/qrcode", response_model=QrcodeStartResponse)
async def start_qrcode_login(_: CurrentUser):
    try:
        qrcode = await get_tv_qrcode()
    except BilibiliQrcodeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    url = qrcode["data"]["url"]
    return QrcodeStartResponse(url=url, qrcode=qrcode)


@router.post("/login/qrcode/poll", response_model=QrcodeLoginResponse)
async def poll_qrcode_login(request: Request, body: QrcodePollRequest, user: CurrentUser):
    try:
        login_data = await poll_tv_qrcode_login(body.qrcode)
        cookie_header = cookie_info_to_header(login_data["cookie_info"])
    except BilibiliQrcodeError as exc:
        detail = str(exc)
        if "超时" in detail:
            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    svc = get_config_service()
    await svc.set_settings({"bilibili_cookie_encrypted": encrypt_value(cookie_header)})
    await svc.reload()
    await reload_all_monitors()

    conn = await get_bilibili_connection_status()
    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details(
            {
                "bilibili_cookie_encrypted": "***",
                "source": "qrcode_login",
                "uid": conn.get("uid"),
            }
        ),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Bilibili cookie updated via QR login")

    if not conn.get("logged_in"):
        return QrcodeLoginResponse(
            success=False,
            message=bilibili_status_message(conn) or "Cookie 已保存，但登录验证未通过",
        )

    return QrcodeLoginResponse(
        success=True,
        username=conn.get("username"),
        uid=conn.get("uid"),
        message=bilibili_status_message(conn) or "登录成功",
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout_bilibili(request: Request, user: CurrentUser):
    svc = get_config_service()
    snap = svc.get_snapshot()
    if not snap.bilibili_cookie_set:
        return LogoutResponse(success=True, message="当前未登录 B 站")

    await svc.set_settings({"bilibili_cookie_encrypted": ""})
    await svc.reload()
    await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details(
            {
                "bilibili_cookie_encrypted": "",
                "source": "bilibili_logout",
            }
        ),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Bilibili cookie cleared via logout")

    return LogoutResponse(success=True, message="已退出 B 站登录")
