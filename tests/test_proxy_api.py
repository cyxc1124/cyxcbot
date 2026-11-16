"""Proxy tests reuse a saved password only for the saved host and report per service."""

import json

import ai_image_helpers  # noqa: F401
import httpx
import pytest
from fastapi import HTTPException

from admin.api.v1 import proxies as proxies_api
from admin.schemas.proxies import ProxyTestRequest
from admin.services import proxy_check
from shared.config.proxies import ProxyRecord, load_proxies, probe_proxy
from shared.config.proxy import ProxyConfig
from shared.config.types import AppConfigSnapshot

SAVED = ProxyRecord(
    id="p1",
    name="香港",
    scheme="socks5",
    host="hk.proxy.test",
    port=1080,
    username="user",
    password="saved-pass-test-only",
    password_set=True,
)
REAL_CLIENT = httpx.AsyncClient


def test_saved_password_only_follows_the_saved_host():
    same = probe_proxy(
        (SAVED,),
        proxy_id="p1",
        scheme="http",
        host="HK.proxy.test",
        port=8080,
        username="user",
    )
    assert same.to_url() == "http://user:saved-pass-test-only@HK.proxy.test:8080"
    with pytest.raises(ValueError, match="重新填写密码"):
        probe_proxy((SAVED,), proxy_id="p1", scheme="socks5", host="x.test", port=1)
    typed = probe_proxy(
        (SAVED,),
        proxy_id="p1",
        scheme="socks5",
        host="x.test",
        port=1080,
        password="typed",
    )
    assert typed.password == "typed"
    with pytest.raises(ValueError, match="列表已变化"):
        probe_proxy((SAVED,), proxy_id="gone", scheme="http", host="h", port=1)


def test_corrupt_stored_proxies_are_skipped():
    raw = json.dumps(
        [
            {
                "id": "a",
                "name": "A",
                "scheme": "http",
                "host": "h",
                "port": 1,
                "password_encrypted": "not-a-token",
            },
            {"id": "a", "name": "重复", "scheme": "http", "host": "h", "port": 1},
            {"id": "b", "name": "B", "scheme": "ftp", "host": "h", "port": 1},
            {"id": "c", "name": "C", "scheme": "http", "host": "h", "port": 0},
            "junk",
        ]
    )
    (record,) = load_proxies(raw)
    assert (record.id, record.password, record.password_set) == ("a", "", True)
    assert load_proxies("not json") == ()


async def test_proxy_test_endpoint_uses_saved_password_and_summarizes(monkeypatch):
    snapshot = AppConfigSnapshot(proxies=(SAVED,))
    monkeypatch.setattr(
        proxies_api,
        "get_config_service",
        lambda: type("Service", (), {"get_snapshot": lambda self: snapshot})(),
    )
    seen = []

    async def fake_check(proxy):
        seen.append(proxy)
        return [
            proxy_check.ProxyCheck(
                "X API", "https://x", True, "可访问（HTTP 200）", 200, 80
            ),
            proxy_check.ProxyCheck("OpenAI API", "https://o", False, "连接超时"),
        ]

    monkeypatch.setattr(proxies_api, "check_proxy", fake_check)
    body = ProxyTestRequest(id="p1", scheme="socks5", host="hk.proxy.test", port=1080)
    response = await proxies_api.run_proxy_test(body, None)
    assert seen[0].password == "saved-pass-test-only"
    assert not response.success
    assert response.message == "经此代理可访问 1/2 个服务"
    assert [target.reachable for target in response.targets] == [True, False]
    assert "saved-pass" not in response.model_dump_json()

    with pytest.raises(HTTPException) as error:
        await proxies_api.run_proxy_test(
            ProxyTestRequest(id="p1", scheme="socks5", host="evil.test", port=1080),
            None,
        )
    assert error.value.status_code == 400
    assert len(seen) == 1


def _client_factory(monkeypatch, handler):
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return REAL_CLIENT(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(proxy_check.httpx, "AsyncClient", factory)
    return calls


async def test_any_http_response_counts_as_reachable(monkeypatch):
    calls = _client_factory(monkeypatch, lambda request: httpx.Response(401))
    proxy = ProxyConfig(enabled=True, scheme="http", host="proxy.test", port=7890)
    results = await proxy_check.check_proxy(proxy)
    assert [result.name for result in results] == [
        name for name, _ in proxy_check.TARGETS
    ]
    assert all(result.reachable and result.status_code == 401 for result in results)
    assert all(call["proxy"] == "http://proxy.test:7890" for call in calls)
    assert all(call["trust_env"] is False for call in calls)


@pytest.mark.parametrize(
    "error,message",
    [
        (httpx.ProxyError("407"), "代理拒绝了连接"),
        (httpx.ConnectTimeout("slow"), "连接超时"),
        (httpx.ConnectError("refused"), "无法连接到代理"),
        (httpx.ReadError("reset"), "请求失败"),
    ],
)
async def test_failures_are_reported_per_service(monkeypatch, error, message):
    def fail(request):
        raise error

    _client_factory(monkeypatch, fail)
    proxy = ProxyConfig(enabled=True, scheme="socks5", host="proxy.test", port=1080)
    results = await proxy_check.check_proxy(proxy)
    assert all(not result.reachable for result in results)
    assert all(message in result.message for result in results)
