"""Minimal tests for ProxyConfig.to_url."""

from __future__ import annotations

from shared.config.proxy import ProxyConfig


def test_to_url_disabled_returns_none():
    cfg = ProxyConfig(enabled=False, scheme="http", host="127.0.0.1", port=7890)
    assert cfg.to_url() is None
    assert cfg.is_configured is False


def test_to_url_http_without_auth():
    cfg = ProxyConfig(enabled=True, scheme="http", host="127.0.0.1", port=7890)
    assert cfg.to_url() == "http://127.0.0.1:7890"


def test_to_url_socks5_with_auth():
    cfg = ProxyConfig(
        enabled=True,
        scheme="socks5",
        host="proxy.example",
        port=1080,
        username="user",
        password="p@ss",
    )
    assert cfg.to_url() == "socks5://user:p%40ss@proxy.example:1080"


def test_feature_proxy_id_resolves_to_a_connection_or_direct():
    from shared.config.proxies import ProxyRecord, resolve_proxy

    records = (
        ProxyRecord(
            id="p1",
            name="代理",
            scheme="socks5",
            host="proxy.example",
            port=1080,
            username="user",
            password="p@ss",
        ),
    )
    assert resolve_proxy(records, "p1").to_url() == (
        "socks5://user:p%40ss@proxy.example:1080"
    )
    assert resolve_proxy(records, "").to_url() is None
    assert resolve_proxy(records, "deleted").to_url() is None


def test_proxy_password_is_not_in_repr():
    cfg = ProxyConfig(enabled=True, host="h", password="secret-test-only")
    assert "secret-test-only" not in repr(cfg)


def test_create_session_uses_proxy_connector_for_http_and_socks5():
    """HTTP/SOCKS5 沿用 connector，代理覆盖 session 内全部请求。"""
    import asyncio

    from aiohttp_socks import ProxyConnector

    from utils.x_api import create_session

    async def _check(scheme: str) -> None:
        session = create_session(
            ProxyConfig(enabled=True, scheme=scheme, host="127.0.0.1", port=7890)
        )
        try:
            assert isinstance(session.connector, ProxyConnector)
        finally:
            await session.close()

    asyncio.run(_check("http"))
    asyncio.run(_check("socks5"))


def test_create_session_plain_when_proxy_disabled():
    import asyncio

    from aiohttp_socks import ProxyConnector

    from utils.x_api import create_session

    async def _check() -> None:
        session = create_session(
            ProxyConfig(enabled=False, scheme="http", host="127.0.0.1", port=7890)
        )
        try:
            assert not isinstance(session.connector, ProxyConnector)
        finally:
            await session.close()

    asyncio.run(_check())
