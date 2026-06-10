"""Tests for admin.auth.jwt."""

from __future__ import annotations

from admin.auth.jwt import create_access_token, decode_access_token


def test_create_and_decode_access_token() -> None:
    token = create_access_token("admin", {"uid": 1, "is_admin": True})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["uid"] == 1
    assert payload["is_admin"] is True
    assert "exp" in payload


def test_decode_invalid_token_returns_none() -> None:
    assert decode_access_token("invalid.token.value") is None
