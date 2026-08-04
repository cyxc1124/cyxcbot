"""Validate WEB_SECRET_KEY used for JWT signing and Fernet cookie encryption."""

from __future__ import annotations

import os

# Committed placeholders / examples that must never be accepted at runtime.
_INSECURE_WEB_SECRET_KEYS = frozenset(
    {
        "change-me-to-a-long-random-string",
        "changeme",
        "secret",
        "password",
        "your-secret-key",
        "your-random-secret",
    }
)

_MIN_WEB_SECRET_KEY_LENGTH = 32


def require_web_secret_key() -> str:
    """Return WEB_SECRET_KEY or raise ValueError if missing/insecure."""
    secret = os.getenv("WEB_SECRET_KEY", "").strip()
    if not secret:
        raise ValueError("WEB_SECRET_KEY must be set for Web Admin")
    if secret in _INSECURE_WEB_SECRET_KEYS or len(secret) < _MIN_WEB_SECRET_KEY_LENGTH:
        raise ValueError(
            "WEB_SECRET_KEY is missing, too short, or matches a known insecure "
            f"placeholder (min length {_MIN_WEB_SECRET_KEY_LENGTH}; generate a "
            "unique random string before deploy)"
        )
    return secret
