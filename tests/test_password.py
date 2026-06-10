"""Tests for admin.auth.password."""

from __future__ import annotations

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


def test_long_password_truncated_at_72_bytes() -> None:
    """bcrypt 5.x rejects >72-byte passwords; we preserve 4.x truncation behavior."""
    prefix = "a" * 72
    long_password = prefix + "extra-suffix"
    password_hash = hash_password(long_password)
    assert verify_password(long_password, password_hash)
    assert verify_password(prefix, password_hash)


def test_unicode_password_at_byte_boundary() -> None:
    password = "中" * 24  # 72 bytes in UTF-8
    password_hash = hash_password(password)
    assert verify_password(password, password_hash)
