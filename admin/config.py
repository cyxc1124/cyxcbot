"""Web Admin environment configuration."""

from __future__ import annotations

import os
from datetime import timedelta


def get_web_host() -> str:
    return os.getenv("WEB_HOST", "0.0.0.0")


def get_web_port() -> int:
    return int(os.getenv("WEB_PORT", "8081"))


def get_jwt_secret() -> str:
    from shared.security.web_secret import require_web_secret_key

    return require_web_secret_key()


def get_jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def get_jwt_expire_minutes() -> int:
    try:
        return max(15, int(os.getenv("JWT_EXPIRE_MINUTES", "1440")))
    except ValueError:
        return 1440


def get_access_token_expires() -> timedelta:
    return timedelta(minutes=get_jwt_expire_minutes())
