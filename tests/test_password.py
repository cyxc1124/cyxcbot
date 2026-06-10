"""Tests for admin.auth.password."""

from __future__ import annotations

import bcrypt
import pytest

from admin.auth.password import hash_password, verify_password


def test_hash_and_verify_password() -> None:
    password = "secure-password-123"
    password_hash = hash_password(password)
    assert password_hash != password
    assert verify_password(password, password_hash)


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = hash_password("correct-password")
    assert not verify_password("wrong-password", password_hash)


def test_verify_password_rejects_invalid_hash() -> None:
    assert not verify_password("any-password", "not-a-valid-bcrypt-hash")


def test_hash_password_rejects_password_exceeding_72_bytes() -> None:
    with pytest.raises(ValueError, match="密码过长"):
        hash_password("a" * 73)


def test_verify_password_supports_legacy_truncated_hashes() -> None:
    """Hashes created before byte-length validation only stored the first 72 bytes."""
    prefix = "a" * 72
    long_password = prefix + "extra-suffix"
    password_hash = bcrypt.hashpw(prefix.encode(), bcrypt.gensalt()).decode()
    assert verify_password(long_password, password_hash)
    assert verify_password(prefix, password_hash)


def test_unicode_password_at_byte_boundary() -> None:
    password = "中" * 24  # 72 bytes in UTF-8
    password_hash = hash_password(password)
    assert verify_password(password, password_hash)
