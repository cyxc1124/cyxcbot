"""Douyin login endpoints (QR via Playwright + cookie clear)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.douyin import (
    DouyinLogoutResponse,
    DouyinQrcodeLoginResponse,
    DouyinQrcodePollRequest,
    DouyinQrcodeStartResponse,
)
from shared.config.service import get_config_service
from shared.douyin.qrcode_login import (
    DouyinQrcodeError,
    close_qr_session,
    poll_qrcode_login,
    refresh_qrcode_login,
    start_qrcode_login,
)
from shared.security.crypto import encrypt_value, mask_secret
from utils.douyin_api import validate_cookie_header

router = APIRouter(
    prefix="/douyin",
    tags=["douyin"],
    dependencies=[RequireSetup],
)


@router.get("/login/qrcode", response_model=DouyinQrcodeStartResponse)
async def start_douyin_qrcode_login(_: AdminUser):
    try:
        data = await start_qrcode_login()
    except DouyinQrcodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return DouyinQrcodeStartResponse(
        session_id=data["session_id"],
        image_base64=data["image_base64"],
    )


@router.post("/login/qrcode/refresh", response_model=DouyinQrcodeStartResponse)
async def refresh_douyin_qrcode_login(body: DouyinQrcodePollRequest, _: AdminUser):
    try:
        data = await refresh_qrcode_login(body.session_id)
    except DouyinQrcodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return DouyinQrcodeStartResponse(
        session_id=data["session_id"],
        image_base64=data["image_base64"],
    )


@router.post("/login/qrcode/poll", response_model=DouyinQrcodeLoginResponse)
async def poll_douyin_qrcode_login(body: DouyinQrcodePollRequest, _: AdminUser):
    try:
        cookie_header = await poll_qrcode_login(body.session_id)
    except DouyinQrcodeError as exc:
        detail = str(exc)
        if "超时" in detail:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=detail
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=detail
        ) from exc

    if not cookie_header.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="登录成功但未获取到 Cookie",
        )

    svc = get_config_service()
    await svc.set_settings({"douyin_cookie_encrypted": encrypt_value(cookie_header)})
    await svc.reload()
    snap = svc.get_snapshot()
    preview = mask_secret(snap.douyin_cookie) if snap.douyin_cookie else None

    keys_ok = validate_cookie_header(cookie_header)
    message = "抖音扫码登录成功"
    if not keys_ok:
        message = (
            "抖音扫码登录成功，但 Cookie 可能缺少部分建议字段"
            "（ttwid / odin_tt / passport_csrf_token）"
        )

    return DouyinQrcodeLoginResponse(
        success=True,
        message=message,
        configured=snap.douyin_cookie_set,
        preview=preview,
    )


@router.post("/login/qrcode/cancel")
async def cancel_douyin_qrcode_login(body: DouyinQrcodePollRequest, _: AdminUser):
    await close_qr_session(body.session_id)
    return {"success": True, "message": "已取消扫码登录"}


@router.post("/logout", response_model=DouyinLogoutResponse)
async def logout_douyin(_: AdminUser):
    svc = get_config_service()
    snap = svc.get_snapshot()
    if not snap.douyin_cookie_set:
        return DouyinLogoutResponse(success=True, message="当前未配置抖音 Cookie")

    await svc.set_settings({"douyin_cookie_encrypted": ""})
    await svc.reload()
    return DouyinLogoutResponse(success=True, message="已退出抖音登录")
