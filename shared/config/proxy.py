"""Outbound HTTP/SOCKS proxy configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

_ALLOWED_SCHEMES = frozenset({"http", "https", "socks5"})


@dataclass
class ProxyConfig:
    """Proxy settings used by outbound HTTP clients (e.g. X API)."""

    enabled: bool = False
    scheme: str = "http"
    host: str = ""
    port: int = 7890
    username: str = ""
    password: str = ""

    @classmethod
    def from_settings(cls, settings: dict) -> "ProxyConfig":
        scheme = str(settings.get("x_proxy_scheme", "http") or "http").strip().lower()
        if scheme not in _ALLOWED_SCHEMES:
            scheme = "http"
        try:
            port = int(settings.get("x_proxy_port", 7890))
        except TypeError, ValueError:
            port = 7890
        port = max(1, min(65535, port))
        return cls(
            enabled=bool(settings.get("x_proxy_enabled", False)),
            scheme=scheme,
            host=str(settings.get("x_proxy_host", "") or "").strip(),
            port=port,
            username=str(settings.get("x_proxy_username", "") or ""),
            password=str(settings.get("x_proxy_password", "") or ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.host and 1 <= self.port <= 65535)

    def to_url(self) -> Optional[str]:
        if not self.is_configured:
            return None
        if self.scheme not in _ALLOWED_SCHEMES:
            return None
        auth = ""
        if self.username:
            user = quote(self.username, safe="")
            if self.password:
                auth = f"{user}:{quote(self.password, safe='')}@"
            else:
                auth = f"{user}@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"
