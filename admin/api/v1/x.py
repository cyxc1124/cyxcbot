"""X (Twitter) Bearer Token endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.x import (
    XBearerSaveRequest,
    XBearerStatusResponse,
    XBearerTestRequest,
    XBearerTestResponse,
)
from admin.services.target_metadata import resolve_x_user
from shared.config.service import get_config_service
from shared.security.crypto import encrypt_value, mask_secret

router = APIRouter(
    prefix="/x",
    tags=["x"],
    dependencies=[RequireSetup],
)


@router.get("/bearer", response_model=XBearerStatusResponse)
async def get_x_bearer_status(_: AdminUser):
    snap = get_config_service().get_snapshot()
    preview = mask_secret(snap.x_api_bearer) if snap.x_api_bearer else None
    return XBearerStatusResponse(
        configured=snap.x_api_bearer_set,
        preview=preview,
        message="已配置" if snap.x_api_bearer_set else "未配置",
    )


@router.put("/bearer", response_model=XBearerStatusResponse)
async def save_x_bearer(body: XBearerSaveRequest, _: AdminUser):
    bearer = body.bearer.strip()
    if not bearer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bearer Token 不能为空"
        )
    svc = get_config_service()
    await svc.set_settings({"x_api_bearer_encrypted": encrypt_value(bearer)})
    await svc.reload()
    snap = svc.get_snapshot()
    return XBearerStatusResponse(
        configured=snap.x_api_bearer_set,
        preview=mask_secret(snap.x_api_bearer) if snap.x_api_bearer else None,
        message="X API Bearer Token 已保存",
    )


@router.delete("/bearer", response_model=XBearerStatusResponse)
async def clear_x_bearer(_: AdminUser):
    svc = get_config_service()
    snap = svc.get_snapshot()
    if not snap.x_api_bearer_set:
        return XBearerStatusResponse(
            configured=False, preview=None, message="当前未配置 Bearer Token"
        )
    await svc.set_settings({"x_api_bearer_encrypted": ""})
    await svc.reload()
    return XBearerStatusResponse(
        configured=False, preview=None, message="已清除 X API Bearer Token"
    )


@router.post("/bearer/test", response_model=XBearerTestResponse)
async def test_x_bearer(body: XBearerTestRequest, _: AdminUser):
    snap = get_config_service().get_snapshot()
    if not snap.x_api_bearer_set:
        return XBearerTestResponse(
            success=False,
            message="未配置 Bearer Token",
        )

    username = body.username.lstrip("@").strip() or "X"
    user = await resolve_x_user(username)
    if not user:
        return XBearerTestResponse(
            success=False,
            message=f"无法查询用户 @{username}，请检查 Token、代理或用户名",
            username=username,
        )

    return XBearerTestResponse(
        success=True,
        message=f"连接成功：@{user.username}",
        username=user.username,
        name=user.name or None,
        user_id=user.id,
    )
