"""AI image detection vision providers: save each one, list models, test, read balances."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Path

from admin.deps import AdminUser, RequireSetup
from admin.schemas.ai_image import (
    VisionBalance,
    VisionBalanceItem,
    VisionBalanceResponse,
    VisionModelInfo,
    VisionModelsResponse,
    VisionProbeRequest,
    VisionProviderCreate,
    VisionProviderPatch,
    VisionProvidersResponse,
    VisionTestResponse,
)
from shared.config.ai_image import (
    VisionProviderRecord,
    probe_provider,
    vision_providers_for_api,
)
from shared.config.proxy import ProxyConfig
from shared.config.service import get_config_service
from utils.vision_api import (
    VisionAPIError,
    judge_image,
    list_models,
    query_balance,
    sample_image,
)

router = APIRouter(
    prefix="/ai-image",
    tags=["ai-image"],
    dependencies=[RequireSetup],
)


ProviderId = Path(min_length=1, max_length=32)
_MISSING = "视觉模型不存在或已被删除，请刷新页面后重试"


def _providers(saved_id: str | None = None) -> VisionProvidersResponse:
    snapshot = get_config_service().get_snapshot()
    return VisionProvidersResponse(
        id=saved_id,
        providers=vision_providers_for_api(snapshot.ai_image_vision_providers),
    )


async def _save(provider_id: str | None, changes: dict) -> VisionProvidersResponse:
    try:
        saved_id = await get_config_service().upsert_vision_provider(
            provider_id, changes
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=_MISSING) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _providers(saved_id)


@router.post("/vision/providers", response_model=VisionProvidersResponse)
async def create_vision_provider(body: VisionProviderCreate, _: AdminUser):
    return await _save(None, body.model_dump())


@router.patch("/vision/providers/{provider_id}", response_model=VisionProvidersResponse)
async def update_vision_provider(
    body: VisionProviderPatch, _: AdminUser, provider_id: str = ProviderId
):
    # 显式传 null 与省略同义：不修改该字段（api_key 为 null 即保留密钥）。
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None
    }
    return await _save(provider_id, changes)


@router.delete(
    "/vision/providers/{provider_id}", response_model=VisionProvidersResponse
)
async def delete_vision_provider(_: AdminUser, provider_id: str = ProviderId):
    try:
        await get_config_service().remove_vision_provider(provider_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=_MISSING) from None
    return _providers()


def _provider(
    body: VisionProbeRequest, *, require_model: bool = False
) -> tuple[VisionProviderRecord, ProxyConfig | None]:
    snapshot = get_config_service().get_snapshot()
    try:
        provider = probe_provider(
            snapshot.ai_image_vision_providers,
            provider_id=body.id,
            api_type=body.api_type,
            base_url=body.base_url,
            model=body.model,
            proxy_id=body.proxy_id,
            api_key=body.api_key,
            require_model=require_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if body.proxy_id and all(proxy.id != body.proxy_id for proxy in snapshot.proxies):
        raise HTTPException(
            status_code=400, detail="所选代理不存在，请刷新页面后重新选择"
        )
    return provider, snapshot.proxy(body.proxy_id)


def _failure(exc: VisionAPIError) -> str:
    # 管理员排障需要上游原文；群聊回复只用 exc.message。
    return f"{exc.message}（{exc.detail}）" if exc.detail else exc.message


@router.post("/vision/models", response_model=VisionModelsResponse)
async def list_vision_models(body: VisionProbeRequest, _: AdminUser):
    provider, proxy = _provider(body)
    try:
        models = await list_models(provider, proxy=proxy)
    except VisionAPIError as exc:
        return VisionModelsResponse(success=False, message=_failure(exc))
    flagged = sum(model.vision is True for model in models)
    message = f"已获取 {len(models)} 个模型"
    if flagged:
        message += f"，其中 {flagged} 个声明支持图片输入"
    return VisionModelsResponse(
        success=True,
        message=message,
        models=[
            VisionModelInfo(id=model.id, name=model.name, vision=model.vision)
            for model in models
        ],
    )


@router.post("/vision/test", response_model=VisionTestResponse)
async def run_vision_test(body: VisionProbeRequest, _: AdminUser):
    provider, proxy = _provider(body, require_model=True)
    started = time.perf_counter()
    try:
        verdict = await judge_image(provider, sample_image(), proxy=proxy)
    except VisionAPIError as exc:
        return VisionTestResponse(
            success=False,
            message=_failure(exc),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
    return VisionTestResponse(
        success=True,
        message="模型响应正常，返回了约定的判断格式",
        latency_ms=round((time.perf_counter() - started) * 1000),
        verdict=verdict.verdict,
        confidence=verdict.confidence,
        reason=verdict.reason,
        input_tokens=verdict.input_tokens,
        output_tokens=verdict.output_tokens,
    )


@router.post("/vision/balance", response_model=VisionBalanceResponse)
async def get_vision_balance(body: VisionProbeRequest, _: AdminUser):
    provider, proxy = _provider(body)
    try:
        result = await query_balance(provider, proxy=proxy)
    except VisionAPIError as exc:
        return VisionBalanceResponse(success=False, message=_failure(exc))
    return VisionBalanceResponse(
        success=True,
        message=f"已获取 {result.provider} 余额",
        provider=result.provider,
        available=result.available,
        balances=[
            VisionBalance(
                currency=balance.currency,
                total=balance.total,
                items=[
                    VisionBalanceItem(label=item.label, amount=item.amount)
                    for item in balance.items
                ],
            )
            for balance in result.balances
        ],
    )
