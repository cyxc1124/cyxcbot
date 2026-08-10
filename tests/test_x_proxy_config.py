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
