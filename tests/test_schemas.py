"""Tests for Pydantic API schemas."""

from __future__ import annotations

import bcrypt
import pytest
from pydantic import ValidationError

from admin.auth.password import verify_password
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


@pytest.mark.parametrize(
    "password",
    ["a" * 73, "中" * 25, "a" * 71 + "中", "😀" * 128],
)
def test_login_request_accepts_legacy_password_exceeding_72_utf8_bytes(
    password: str,
) -> None:
    password_hash = bcrypt.hashpw(
        password.encode("utf-8")[:72], bcrypt.gensalt()
    ).decode()
    req = LoginRequest(username="admin", password=password)
    assert req.password == password
    assert verify_password(req.password, password_hash)


def test_login_request_accepts_password_at_72_utf8_byte_boundary() -> None:
    req = LoginRequest(username="admin", password="a" * 72)
    assert len(req.password.encode("utf-8")) == 72


def test_setup_request_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        SetupRequest(username="admin", password="short")


@pytest.mark.parametrize("password", ["a" * 73, "中" * 25, "a" * 71 + "中"])
def test_setup_request_rejects_password_exceeding_72_utf8_bytes(password: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        SetupRequest(username="admin", password=password)
    assert any("密码过长" in error["msg"] for error in exc_info.value.errors())
