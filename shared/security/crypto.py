"""Fernet encryption for sensitive values (e.g. Bilibili cookie)."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a stable Fernet key from WEB_SECRET_KEY."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    secret = os.getenv("WEB_SECRET_KEY", "")
    if not secret:
        raise ValueError("WEB_SECRET_KEY is not configured")
    return Fernet(_derive_fernet_key(secret))


def encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return ""
    token = get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt value; check WEB_SECRET_KEY") from exc


def mask_secret(value: str, visible: int = 4) -> str:
    """Mask a secret for API responses."""
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"
