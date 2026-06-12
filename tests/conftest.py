"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def web_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "WEB_SECRET_KEY",
        "test-secret-key-for-pytest-only-not-for-production",
    )
