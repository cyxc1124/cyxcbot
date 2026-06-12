"""Tests for shared.security.crypto."""

from __future__ import annotations

import pytest

from shared.security.crypto import (
    decrypt_value,
    encrypt_value,
    get_fernet,
    mask_secret,
)


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "SESSDATA=abc123;bili_jct=xyz"
    ciphertext = encrypt_value(plaintext)
    assert ciphertext
    assert ciphertext != plaintext
    assert decrypt_value(ciphertext) == plaintext


def test_encrypt_empty_returns_empty() -> None:
    assert encrypt_value("") == ""
    assert decrypt_value("") == ""


def test_decrypt_with_wrong_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    ciphertext = encrypt_value("secret-cookie")
    monkeypatch.setenv("WEB_SECRET_KEY", "different-secret-key-for-pytest")
    with pytest.raises(ValueError, match="Failed to decrypt"):
        decrypt_value(ciphertext)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("abc", "***"),
        ("123456789012", "1234...9012"),
        ("short", "*****"),
    ],
)
def test_mask_secret(value: str, expected: str) -> None:
    assert mask_secret(value) == expected


def test_get_fernet_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WEB_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="WEB_SECRET_KEY"):
        get_fernet()
