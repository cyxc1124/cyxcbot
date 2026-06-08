"""Web Admin environment configuration."""

from __future__ import annotations

import os
from datetime import timedelta


def get_web_host() -> str:
    return os.getenv("WEB_HOST", "0.0.0.0")


def get_web_port() -> int:
    return int(os.getenv("WEB_PORT", "8081"))


def get_jwt_secret() -> str:
    secret = os.getenv("WEB_SECRET_KEY", "")
    if not secret:
        raise ValueError("WEB_SECRET_KEY must be set for Web Admin")
    return secret


def get_jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def get_jwt_expire_minutes() -> int:
    try:
        return max(15, int(os.getenv("JWT_EXPIRE_MINUTES", "1440")))
    except ValueError:
        return 1440


def get_access_token_expires() -> timedelta:
    return timedelta(minutes=get_jwt_expire_minutes())
