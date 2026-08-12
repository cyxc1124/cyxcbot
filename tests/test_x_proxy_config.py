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


def test_from_settings_rejects_unknown_scheme():
    cfg = ProxyConfig.from_settings(
        {
            "x_proxy_enabled": True,
            "x_proxy_scheme": "ftp",
            "x_proxy_host": "127.0.0.1",
            "x_proxy_port": 1080,
        }
    )
    assert cfg.scheme == "http"
    assert cfg.to_url() == "http://127.0.0.1:1080"


def test_from_settings_clamps_port():
    cfg = ProxyConfig.from_settings(
        {
            "x_proxy_enabled": True,
            "x_proxy_scheme": "socks5",
            "x_proxy_host": "h",
            "x_proxy_port": 99999,
        }
    )
    assert cfg.port == 65535


def test_create_session_uses_proxy_connector_for_http_and_socks5():
    """http/https/socks5 都必须挂在 connector 上，避免 API/t.co 部分直连。"""
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
    asyncio.run(_check("https"))
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
