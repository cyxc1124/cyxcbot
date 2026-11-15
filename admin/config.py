"""Web Admin environment configuration."""

from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import urlsplit


def get_web_host() -> str:
    return os.getenv("WEB_HOST", "0.0.0.0")


def get_web_port() -> int:
    return int(os.getenv("WEB_PORT", "8081"))


def get_web_public_origin() -> str | None:
    value = os.getenv("WEB_PUBLIC_ORIGIN", "").strip()
    if not value:
        return None
    try:
        origin = urlsplit(value)
        if (
            origin.scheme not in ("http", "https")
            or not origin.hostname
            or any(char.isspace() for char in origin.hostname)
            or origin.username is not None
            or origin.password is not None
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
        ):
            raise ValueError
        host = origin.hostname.encode("idna").decode("ascii")
        if ":" in host:
            host = f"[{host}]"
        port = origin.port
        if port is not None and port != (443 if origin.scheme == "https" else 80):
            host += f":{port}"
        return f"{origin.scheme}://{host}"
    except ValueError, UnicodeError:
        raise ValueError(
            "WEB_PUBLIC_ORIGIN must be an HTTP(S) origin without a path"
        ) from None


def get_jwt_secret() -> str:
    from shared.security.web_secret import require_web_secret_key

    return require_web_secret_key()


_JWT_ALGORITHMS = ("HS256", "HS384", "HS512")


def get_jwt_algorithm() -> str:
    # 密钥是对称的，只允许 HMAC；避免误配成 none 或非对称算法。
    value = os.getenv("JWT_ALGORITHM", "HS256").strip().upper()
    if value not in _JWT_ALGORITHMS:
        raise ValueError(f"JWT_ALGORITHM must be one of {', '.join(_JWT_ALGORITHMS)}")
    return value


def get_jwt_expire_minutes() -> int:
    try:
        return max(15, int(os.getenv("JWT_EXPIRE_MINUTES", "1440")))
    except ValueError:
        return 1440


def get_access_token_expires() -> timedelta:
    return timedelta(minutes=get_jwt_expire_minutes())
