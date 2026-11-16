"""Shared outbound proxies: save each one, delete unused ones, test connectivity."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from admin.deps import AdminUser, RequireSetup
from admin.schemas.proxies import (
    ProxiesResponse,
    ProxyCreate,
    ProxyPatch,
    ProxyTestRequest,
    ProxyTestResponse,
    ProxyTestTarget,
)
from admin.services.proxy_check import check_proxy
from shared.config.proxies import ProxyInUseError, probe_proxy, proxies_for_api
from shared.config.service import get_config_service

router = APIRouter(
    prefix="/proxies",
    tags=["proxies"],
    dependencies=[RequireSetup],
)

ProxyId = Path(min_length=1, max_length=32)
_MISSING = "代理不存在或已被删除，请刷新页面后重试"


def _proxies(saved_id: str | None = None) -> ProxiesResponse:
    snapshot = get_config_service().get_snapshot()
    return ProxiesResponse(id=saved_id, proxies=proxies_for_api(snapshot.proxies))


async def _save(proxy_id: str | None, changes: dict) -> ProxiesResponse:
    try:
        saved_id = await get_config_service().upsert_proxy(proxy_id, changes)
    except KeyError:
        raise HTTPException(status_code=404, detail=_MISSING) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _proxies(saved_id)


@router.post("", response_model=ProxiesResponse)
async def create_proxy(body: ProxyCreate, _: AdminUser):
    return await _save(None, body.model_dump())


@router.patch("/{proxy_id}", response_model=ProxiesResponse)
async def update_proxy(body: ProxyPatch, _: AdminUser, proxy_id: str = ProxyId):
    # 显式传 null 与省略同义：不修改该字段（password 为 null 即保留密码）。
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None
    }
    return await _save(proxy_id, changes)


@router.delete("/{proxy_id}", response_model=ProxiesResponse)
async def delete_proxy(_: AdminUser, proxy_id: str = ProxyId):
    try:
        await get_config_service().remove_proxy(proxy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=_MISSING) from None
    except ProxyInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return _proxies()


@router.post("/test", response_model=ProxyTestResponse)
async def run_proxy_test(body: ProxyTestRequest, _: AdminUser):
    snapshot = get_config_service().get_snapshot()
    try:
        proxy = probe_proxy(
            snapshot.proxies,
            proxy_id=body.id,
            scheme=body.scheme,
            host=body.host,
            port=body.port,
            username=body.username,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    results = await check_proxy(proxy)
    reachable = sum(result.reachable for result in results)
    return ProxyTestResponse(
        success=reachable == len(results),
        message=f"经此代理可访问 {reachable}/{len(results)} 个服务",
        targets=[
            ProxyTestTarget(
                name=result.name,
                url=result.url,
                reachable=result.reachable,
                message=result.message,
                status_code=result.status_code,
                latency_ms=result.latency_ms,
            )
            for result in results
        ],
    )
