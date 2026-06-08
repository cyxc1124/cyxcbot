"""JWT token helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from jose import JWTError, jwt

from admin.config import get_access_token_expires, get_jwt_algorithm, get_jwt_secret


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    expire = datetime.now(timezone.utc) + get_access_token_expires()
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[get_jwt_algorithm()])
    except JWTError:
        return None
