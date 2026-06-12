"""Tests for pruning persisted monitor state when targets are disabled."""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from unittest.mock import MagicMock

import nonebot
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


def _ensure_real_db_modules():
    existing = sys.modules.get("shared.db.models")
    if existing is not None and not isinstance(existing, MagicMock):
        user = getattr(existing, "User", None)
        if user is not None and not isinstance(user, MagicMock):
            from shared.config.service import ConfigService
            from shared.db.base import Model
            from shared.db.models import DynamicMonitorState, DynamicTarget

            return ConfigService, Model, DynamicMonitorState, DynamicTarget

    for name in (
        "shared.config.service",
        "shared.db.models",
        "shared.db.base",
        "nonebot_plugin_orm",
    ):
        module = sys.modules.get(name)
        if module is not None and isinstance(module, MagicMock):
            del sys.modules[name]

    os.environ["SQLALCHEMY_DATABASE_URL"] = _shared_sqlite_url()
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=os.environ["SQLALCHEMY_DATABASE_URL"],
            alembic_startup_check=False,
        )
        nonebot.load_plugin("nonebot_plugin_orm")

    import shared.db.base
    import shared.db.models

    importlib.reload(shared.db.base)
    importlib.reload(shared.db.models)

    if "shared.config.service" in sys.modules:
        importlib.reload(sys.modules["shared.config.service"])

    from shared.config.service import ConfigService
    from shared.db.base import Model
    from shared.db.models import DynamicMonitorState, DynamicTarget

    return ConfigService, Model, DynamicMonitorState, DynamicTarget


@pytest.fixture
async def db_context():
    ConfigService, Model, DynamicMonitorState, DynamicTarget = _ensure_real_db_modules()

    engine = create_async_engine(_shared_sqlite_url())
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield ConfigService, factory, DynamicMonitorState, DynamicTarget
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_config_load_prunes_disabled_dynamic_monitor_state(
    db_context: tuple[
        type,
        async_sessionmaker[AsyncSession],
        type,
        type,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ConfigService, factory, DynamicMonitorState, DynamicTarget = db_context

    async with factory() as session:
        async with session.begin():
            session.add(DynamicTarget(uid="111", enabled=True))
            session.add(DynamicTarget(uid="222", enabled=False))
            session.add(
                DynamicMonitorState(uid="111", last_dynamic_id=100, initialized=True)
            )
            session.add(
                DynamicMonitorState(uid="222", last_dynamic_id=200, initialized=True)
            )

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )

    service = ConfigService()
    await service.load()

    async with factory() as session:
        active = await session.get(DynamicMonitorState, "111")
        removed = await session.get(DynamicMonitorState, "222")

    assert active is not None
    assert active.last_dynamic_id == 100
    assert removed is None


@pytest.mark.asyncio
async def test_config_load_prunes_orphaned_dynamic_monitor_state(
    db_context: tuple[
        type,
        async_sessionmaker[AsyncSession],
        type,
        type,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State for a deleted target (no DynamicTarget row) should be removed."""
    ConfigService, factory, DynamicMonitorState, DynamicTarget = db_context

    async with factory() as session:
        async with session.begin():
            session.add(DynamicTarget(uid="111", enabled=True))
            session.add(
                DynamicMonitorState(uid="111", last_dynamic_id=100, initialized=True)
            )
            session.add(
                DynamicMonitorState(uid="999", last_dynamic_id=900, initialized=True)
            )

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )

    service = ConfigService()
    await service.load()

    async with factory() as session:
        active = await session.get(DynamicMonitorState, "111")
        orphaned = await session.get(DynamicMonitorState, "999")

    assert active is not None
    assert orphaned is None


@pytest.mark.asyncio
async def test_config_load_prunes_all_states_when_no_enabled_targets(
    db_context: tuple[
        type,
        async_sessionmaker[AsyncSession],
        type,
        type,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every target is disabled, all persisted states should be cleared."""
    ConfigService, factory, DynamicMonitorState, DynamicTarget = db_context

    async with factory() as session:
        async with session.begin():
            session.add(DynamicTarget(uid="111", enabled=False))
            session.add(DynamicTarget(uid="222", enabled=False))
            session.add(
                DynamicMonitorState(uid="111", last_dynamic_id=100, initialized=True)
            )
            session.add(
                DynamicMonitorState(uid="222", last_dynamic_id=200, initialized=True)
            )

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )

    service = ConfigService()
    await service.load()

    async with factory() as session:
        state_111 = await session.get(DynamicMonitorState, "111")
        state_222 = await session.get(DynamicMonitorState, "222")

    assert state_111 is None
    assert state_222 is None
