"""Tests for atomic group special title daily quota."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from unittest.mock import MagicMock

import nonebot
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


def _ensure_real_db_modules():
    existing = sys.modules.get("shared.db.models")
    if existing is not None and not isinstance(existing, MagicMock):
        model = getattr(existing, "GroupSpecialTitleUsage", None)
        if model is not None and not isinstance(model, MagicMock):
            from shared.db.base import Model
            from shared.db.models import GroupSpecialTitleUsage

            return Model, GroupSpecialTitleUsage

    for name in (
        "plugins.group_special_title.usage_store",
        "shared.db.models",
        "shared.db.base",
        "nonebot_plugin_orm",
    ):
        sys.modules.pop(name, None)

    os.environ["SQLALCHEMY_DATABASE_URL"] = _shared_sqlite_url()
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=os.environ["SQLALCHEMY_DATABASE_URL"],
            alembic_startup_check=False,
        )
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")

    import shared.db.base  # noqa: F401 — register ORM metadata
    from shared.db.base import Model
    from shared.db.models import GroupSpecialTitleUsage

    return Model, GroupSpecialTitleUsage


@pytest.fixture
async def db_context():
    Model, GroupSpecialTitleUsage = _ensure_real_db_modules()
    engine = create_async_engine(_shared_sqlite_url())
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield engine, factory, GroupSpecialTitleUsage
    finally:
        await engine.dispose()


@pytest.fixture
def usage_store(db_context, monkeypatch: pytest.MonkeyPatch):
    _, factory, _ = db_context
    from plugins.group_special_title import usage_store as store

    monkeypatch.setattr(store, "get_session", lambda: factory())
    monkeypatch.setattr(store, "today_usage_date", lambda: "2026-07-04")
    return store


@pytest.mark.asyncio
async def test_try_consume_respects_daily_limit(usage_store) -> None:
    assert await usage_store.try_consume_daily_quota("1", "2", 2) is True
    assert await usage_store.try_consume_daily_quota("1", "2", 2) is True
    assert await usage_store.try_consume_daily_quota("1", "2", 2) is False


@pytest.mark.asyncio
async def test_release_daily_quota_after_failed_api(usage_store) -> None:
    assert await usage_store.try_consume_daily_quota("1", "2", 1) is True
    await usage_store.release_daily_quota("1", "2")
    assert await usage_store.try_consume_daily_quota("1", "2", 1) is True


@pytest.mark.asyncio
async def test_concurrent_first_use_allows_only_one_when_limit_is_one(
    db_context,
    usage_store,
) -> None:
    _, factory, GroupSpecialTitleUsage = db_context
    results = await asyncio.gather(
        usage_store.try_consume_daily_quota("1", "2", 1),
        usage_store.try_consume_daily_quota("1", "2", 1),
    )

    assert sorted(results) == [False, True]

    async with factory() as session:
        row = await session.scalar(
            select(GroupSpecialTitleUsage).where(
                GroupSpecialTitleUsage.group_id == "1",
                GroupSpecialTitleUsage.user_id == "2",
                GroupSpecialTitleUsage.usage_date == "2026-07-04",
            )
        )
    assert row is not None
    assert row.count == 1


@pytest.mark.asyncio
async def test_concurrent_consume_never_exceeds_limit(
    db_context,
    usage_store,
) -> None:
    _, factory, GroupSpecialTitleUsage = db_context
    daily_limit = 3
    results = await asyncio.gather(
        *(
            usage_store.try_consume_daily_quota("9", "8", daily_limit)
            for _ in range(10)
        )
    )

    assert sum(results) == daily_limit

    async with factory() as session:
        row = await session.scalar(
            select(GroupSpecialTitleUsage).where(
                GroupSpecialTitleUsage.group_id == "9",
                GroupSpecialTitleUsage.user_id == "8",
                GroupSpecialTitleUsage.usage_date == "2026-07-04",
            )
        )
    assert row is not None
    assert row.count == daily_limit
