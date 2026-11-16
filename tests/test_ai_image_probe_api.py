"""Admin probes reuse saved keys only for their saved endpoint and never echo them."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import ai_image_helpers  # noqa: F401
import pytest
from fastapi import HTTPException

from admin.api.v1 import ai_image as probe_api
from admin.schemas.ai_image import VisionProbeRequest
from shared.config.ai_image import VisionProviderRecord, probe_provider
from shared.config.proxies import ProxyRecord
from shared.config.proxy import ProxyConfig
from shared.config.types import AppConfigSnapshot
from utils.vision_api import (
    Balance,
    BalanceItem,
    BalanceResult,
    ModelInfo,
    VisionAPIError,
    VisionVerdict,
)

PROXY_RECORD = ProxyRecord(
    id="px", name="测试代理", scheme="http", host="proxy.test", port=7890
)
PROXY = PROXY_RECORD.to_config()
SAVED = VisionProviderRecord(
    id="p1",
    name="DeepSeek",
    api_type="openai",
    model="deepseek-flash",
    base_url="https://api.deepseek.com",
    api_key="sk-saved-test-only",
    api_key_set=True,
)


@pytest.fixture
def snapshot(monkeypatch):
    state = AppConfigSnapshot(
        ai_image_vision_providers=(SAVED,), proxies=(PROXY_RECORD,)
    )
    monkeypatch.setattr(
        probe_api,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: state),
    )
    return state


def _request(**changes):
    values = {
        "id": "p1",
        "api_type": "openai",
        "base_url": "https://api.deepseek.com/",
        "model": "deepseek-flash",
        "proxy_id": "px",
    }
    return VisionProbeRequest(**{**values, **changes})


def test_saved_key_only_follows_the_saved_endpoint():
    same = probe_provider(
        (SAVED,),
        provider_id="p1",
        api_type="openai",
        base_url="https://api.deepseek.com/",
    )
    assert same.api_key == "sk-saved-test-only"
    for changes in (
        {"base_url": "https://other.test/v1"},
        {"api_type": "anthropic", "base_url": "https://api.deepseek.com"},
    ):
        with pytest.raises(ValueError, match="重新填写 API Key"):
            probe_provider(
                (SAVED,), provider_id="p1", **{"api_type": "openai", **changes}
            )
    typed = probe_provider(
        (SAVED,),
        provider_id="p1",
        api_type="openai",
        base_url="https://other.test/v1",
        api_key="sk-new-test-only",
    )
    assert typed.api_key == "sk-new-test-only"
    cleared = probe_provider(
        (SAVED,), provider_id="p1", api_type="openai", base_url="", api_key=""
    )
    assert cleared.api_key == "" and not cleared.api_key_set
    new = probe_provider((SAVED,), provider_id=None, api_type="anthropic")
    assert (new.api_key, new.endpoint) == ("", "https://api.anthropic.com")
    with pytest.raises(ValueError, match="列表已变化"):
        probe_provider((SAVED,), provider_id="gone", api_type="openai")
    with pytest.raises(ValueError, match="模型不能为空"):
        probe_provider((), provider_id=None, api_type="openai", require_model=True)
    with pytest.raises(ValueError, match="地址"):
        probe_provider((), provider_id=None, api_type="openai", base_url="ftp://x")


async def test_models_use_saved_key_and_provider_proxy(snapshot, monkeypatch):
    calls = AsyncMock(
        return_value=(ModelInfo("deepseek-flash", "", True), ModelInfo("text-only"))
    )
    monkeypatch.setattr(probe_api, "list_models", calls)
    response = await probe_api.list_vision_models(_request(), None)
    provider = calls.await_args.args[0]
    assert provider.api_key == "sk-saved-test-only"
    assert calls.await_args.kwargs == {"proxy": PROXY}
    assert response.success
    assert response.message == "已获取 2 个模型，其中 1 个声明支持图片输入"
    assert [model.vision for model in response.models] == [True, None]
    assert "sk-saved" not in response.model_dump_json()

    await probe_api.list_vision_models(_request(proxy_id=""), None)
    assert calls.await_args.kwargs == {"proxy": ProxyConfig()}
    with pytest.raises(HTTPException) as error:
        await probe_api.list_vision_models(_request(proxy_id="deleted"), None)
    assert error.value.status_code == 400


async def test_endpoint_change_without_key_is_rejected_before_any_request(
    snapshot, monkeypatch
):
    calls = AsyncMock()
    monkeypatch.setattr(probe_api, "list_models", calls)
    with pytest.raises(HTTPException) as error:
        await probe_api.list_vision_models(
            _request(base_url="https://collector.test/v1"), None
        )
    assert error.value.status_code == 400
    calls.assert_not_awaited()


async def test_failures_show_upstream_detail_to_admins(snapshot, monkeypatch):
    monkeypatch.setattr(
        probe_api,
        "query_balance",
        AsyncMock(side_effect=VisionAPIError("API Key 无效。", "Authentication Fails")),
    )
    response = await probe_api.get_vision_balance(_request(), None)
    assert not response.success
    assert response.message == "API Key 无效。（Authentication Fails）"


async def test_response_test_reports_latency_verdict_and_usage(snapshot, monkeypatch):
    judge = AsyncMock(return_value=VisionVerdict("uncertain", 30, "合成渐变", 812, 41))
    monkeypatch.setattr(probe_api, "judge_image", judge)
    response = await probe_api.run_vision_test(_request(api_key="sk-typed"), None)
    assert judge.await_args.args[0].api_key == "sk-typed"
    assert judge.await_args.args[1].media_type == "image/png"
    assert response.success and response.latency_ms is not None
    assert (response.verdict, response.confidence, response.reason) == (
        "uncertain",
        30,
        "合成渐变",
    )
    assert (response.input_tokens, response.output_tokens) == (812, 41)

    judge.side_effect = VisionAPIError("返回内容不是约定的判断格式。", "我觉得是 AI")
    failed = await probe_api.run_vision_test(_request(), None)
    assert not failed.success and "我觉得是 AI" in failed.message
    with pytest.raises(HTTPException, match="模型"):
        await probe_api.run_vision_test(_request(model=" "), None)


async def test_balance_response_lists_currencies(snapshot, monkeypatch):
    monkeypatch.setattr(
        probe_api,
        "query_balance",
        AsyncMock(
            return_value=BalanceResult(
                "DeepSeek",
                True,
                (Balance("CNY", "110.00", (BalanceItem("赠送余额", "10.00"),)),),
            )
        ),
    )
    response = await probe_api.get_vision_balance(_request(), None)
    assert response.success and response.provider == "DeepSeek"
    assert response.available is True
    assert response.balances[0].model_dump() == {
        "currency": "CNY",
        "total": "110.00",
        "items": [{"label": "赠送余额", "amount": "10.00"}],
    }
