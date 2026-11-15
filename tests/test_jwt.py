"""Tests for admin.auth.jwt."""

from __future__ import annotations

from hashlib import sha256

from admin.auth.jwt import create_access_token, decode_access_token


def test_create_and_decode_access_token() -> None:
    token = create_access_token(
        "admin", {"uid": 1, "is_admin": True}, password_hash="stored-bcrypt-hash"
    )
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["uid"] == 1
    assert payload["is_admin"] is True
    assert "exp" in payload
    assert payload["pwd"] == sha256(b"stored-bcrypt-hash").hexdigest()


def test_password_change_changes_token_fingerprint() -> None:
    before = decode_access_token(create_access_token("admin", password_hash="before"))
    after = decode_access_token(create_access_token("admin", password_hash="after"))
    assert before["pwd"] != after["pwd"]


def test_decode_invalid_token_returns_none() -> None:
    assert decode_access_token("invalid.token.value") is None


def test_jwt_algorithm_is_limited_to_hmac(monkeypatch) -> None:
    import pytest

    from admin.config import get_jwt_algorithm

    monkeypatch.setenv("JWT_ALGORITHM", "hs512")
    assert get_jwt_algorithm() == "HS512"
    for value in ("none", "RS256"):
        monkeypatch.setenv("JWT_ALGORITHM", value)
        with pytest.raises(ValueError):
            get_jwt_algorithm()


async def test_web_admin_refuses_to_start_with_invalid_jwt_algorithm(
    monkeypatch,
) -> None:
    import importlib.util
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import nonebot

    driver = MagicMock()
    driver.on_startup = driver.on_shutdown = lambda func: func
    monkeypatch.setattr(nonebot, "get_driver", lambda: driver)
    spec = importlib.util.spec_from_file_location(
        "test_admin_startup", Path(__file__).resolve().parents[1] / "admin/startup.py"
    )
    startup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(startup)

    monkeypatch.setenv("WEB_ADMIN_ENABLED", "true")
    monkeypatch.setenv("WEB_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("JWT_ALGORITHM", "RS256")
    create_app = MagicMock()
    monkeypatch.setitem(
        sys.modules, "admin.app", SimpleNamespace(create_app=create_app)
    )

    await startup.start_web_admin_server()

    create_app.assert_not_called()
