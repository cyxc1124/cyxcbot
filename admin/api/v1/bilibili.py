"""Bilibili login endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.bilibili import (
    BilibiliAccountResponse,
    LogoutResponse,
    QrcodeLoginResponse,
    QrcodePollRequest,
    QrcodeStartResponse,
)
from admin.schemas.connections import BilibiliConnectionStatus
from admin.services.connection_status import (
    bilibili_status_message,
    check_bilibili_cookie,
)
from shared.bilibili.accounts import BilibiliAccount
from shared.bilibili.qrcode_login import (
    BilibiliQrcodeError,
    cookie_info_to_header,
    get_tv_qrcode,
    poll_tv_qrcode_login,
)
from shared.config.service import get_config_service

router = APIRouter(
    prefix="/bilibili",
    tags=["bilibili"],
    dependencies=[RequireSetup],
)


@router.get("/login/qrcode", response_model=QrcodeStartResponse)
async def start_qrcode_login(_: AdminUser):
    try:
        qrcode = await get_tv_qrcode()
    except BilibiliQrcodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    url = qrcode["data"]["url"]
    return QrcodeStartResponse(url=url, qrcode=qrcode)


@router.post("/login/qrcode/poll", response_model=QrcodeLoginResponse)
async def poll_qrcode_login(body: QrcodePollRequest, _: AdminUser):
    try:
        login_data = await poll_tv_qrcode_login(body.qrcode)
        cookie_header = cookie_info_to_header(login_data["cookie_info"])
    except BilibiliQrcodeError as exc:
        detail = str(exc)
        if "超时" in detail:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=detail
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=detail
        ) from exc

    conn = await check_bilibili_cookie(cookie_header)

    if not conn.get("logged_in"):
        return QrcodeLoginResponse(
            success=False,
            message=bilibili_status_message(conn) or "登录验证未通过，未保存账号",
        )

    uid = conn.get("uid")
    if not uid or not uid.isdigit():
        raise HTTPException(
            status_code=502, detail="登录响应未包含有效 UID，未保存账号"
        )
    await get_config_service().upsert_bilibili_account(
        BilibiliAccount(uid=uid, cookie=cookie_header, username=conn.get("username"))
    )

    return QrcodeLoginResponse(
        success=True,
        username=conn.get("username"),
        uid=conn.get("uid"),
        message=bilibili_status_message(conn) or "登录成功",
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout_bilibili(_: AdminUser):
    await get_config_service().remove_bilibili_account()
    return LogoutResponse(success=True, message="已移除全部 B 站账号")


@router.get("/accounts", response_model=list[BilibiliAccountResponse])
async def list_bilibili_accounts(_: AdminUser):
    return [
        BilibiliAccountResponse(uid=row.uid, username=row.username)
        for row in get_config_service().get_snapshot().bilibili_accounts
    ]


@router.post("/accounts/{uid}/test", response_model=BilibiliConnectionStatus)
async def test_bilibili_account(uid: str, _: AdminUser):
    account = next(
        (
            row
            for row in get_config_service().get_snapshot().bilibili_accounts
            if row.uid == uid
        ),
        None,
    )
    if account is None:
        raise HTTPException(status_code=404, detail="B 站账号不存在")
    return await check_bilibili_cookie(account.cookie)


@router.delete("/accounts/{uid}", response_model=LogoutResponse)
async def remove_bilibili_account(uid: str, _: AdminUser):
    try:
        await get_config_service().remove_bilibili_account(uid)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="B 站账号不存在") from exc
    return LogoutResponse(success=True, message="已移除 B 站账号")
