"""Tests for WEB_SECRET_KEY validation."""

from __future__ import annotations

import pytest

from shared.security.web_secret import require_web_secret_key


def test_require_web_secret_key_accepts_strong_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "a" * 32
    monkeypatch.setenv("WEB_SECRET_KEY", secret)
    assert require_web_secret_key() == secret


def test_require_web_secret_key_rejects_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WEB_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="WEB_SECRET_KEY must be set"):
        require_web_secret_key()


@pytest.mark.parametrize(
    "secret",
    [
        "change-me-to-a-long-random-string",
        "changeme",
        "secret",
        "short-secret",
        "x" * 31,
    ],
)
def test_require_web_secret_key_rejects_insecure(
    monkeypatch: pytest.MonkeyPatch, secret: str
) -> None:
    monkeypatch.setenv("WEB_SECRET_KEY", secret)
    with pytest.raises(ValueError, match="insecure|too short|placeholder"):
        require_web_secret_key()
