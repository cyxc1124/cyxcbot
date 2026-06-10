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
