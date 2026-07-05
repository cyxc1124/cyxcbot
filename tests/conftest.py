"""Shared pytest fixtures."""

from __future__ import annotations

import os
import uuid

import pytest

_PROD_DB_MARKERS = ("/data/cyxcbot.db", "cyxcbot.db")


def _pytest_memory_db_url() -> str:
    return (
        f"sqlite+aiosqlite:///file:pytest-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true"
    )


def _looks_like_prod_sqlite(url: str) -> bool:
    return url.startswith("sqlite") and any(
        marker in url for marker in _PROD_DB_MARKERS
    )


# conftest 先于测试模块加载：避免 setdefault / .env 落到 data/cyxcbot.db
if _looks_like_prod_sqlite(os.environ.get("SQLALCHEMY_DATABASE_URL", "")):
    os.environ["SQLALCHEMY_DATABASE_URL"] = _pytest_memory_db_url()


@pytest.fixture(autouse=True)
def _isolate_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("SQLALCHEMY_DATABASE_URL", "")
    if _looks_like_prod_sqlite(url):
        monkeypatch.setenv("SQLALCHEMY_DATABASE_URL", _pytest_memory_db_url())


@pytest.fixture(autouse=True)
def web_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "WEB_SECRET_KEY",
        "test-secret-key-for-pytest-only-not-for-production",
    )
