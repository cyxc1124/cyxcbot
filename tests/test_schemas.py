"""Tests for Pydantic API schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from admin.schemas.common import LoginRequest, SetupRequest


def test_login_request_accepts_valid_credentials() -> None:
    req = LoginRequest(username="admin", password="password123")
    assert req.username == "admin"
    assert req.password == "password123"


@pytest.mark.parametrize(
    "username",
    ["ab", "a" * 65],
)
def test_login_request_rejects_invalid_username(username: str) -> None:
    with pytest.raises(ValidationError):
        LoginRequest(username=username, password="password123")


@pytest.mark.parametrize(
    "password",
    ["short", "a" * 129],
)
def test_login_request_rejects_invalid_password(password: str) -> None:
    with pytest.raises(ValidationError):
        LoginRequest(username="admin", password=password)


def test_setup_request_uses_same_validation_as_login() -> None:
    with pytest.raises(ValidationError):
        SetupRequest(username="admin", password="short")
