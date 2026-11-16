"""Outbound HTTP/SOCKS proxy configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

_ALLOWED_SCHEMES = frozenset({"http", "https", "socks5"})


@dataclass
class ProxyConfig:
    """Resolved proxy for one outbound client; disabled means connect directly."""

    enabled: bool = False
    scheme: str = "http"
    host: str = ""
    port: int = 7890
    username: str = ""
    password: str = field(default="", repr=False)

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
