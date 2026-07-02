"""Tests for batch-loading persisted monitor state (issue #87)."""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import nonebot
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from utils.bilibili_api import LiveStatus

_MONITOR_PLUGIN_MODULES = (
    "plugins.dynamic_monitor.state_store",
    "plugins.dynamic_monitor.dynamic_monitor",
    "plugins.live_monitor.state_store",
    "plugins.live_monitor.live_monitor",
)


def _shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


def _model_column_is_real(model_cls: type, attr: str) -> bool:
    column = getattr(model_cls, attr, None)
    return column is not None and not isinstance(column, MagicMock)


def _ensure_real_db_modules():
    existing = sys.modules.get("shared.db.models")
    if existing is not None and not isinstance(existing, MagicMock):
        user = getattr(existing, "User", None)
        if user is not None and not isinstance(user, MagicMock):
            from shared.db.base import Model
            from shared.db.models import DynamicMonitorState, LiveMonitorState

            if _model_column_is_real(
                DynamicMonitorState, "uid"
            ) and _model_column_is_real(LiveMonitorState, "room_id"):
                for name in (
                    "plugins.dynamic_monitor.state_store",
                    "plugins.live_monitor.state_store",
                ):
                    sys.modules.pop(name, None)
                return Model, DynamicMonitorState, LiveMonitorState

    for name in (
        "shared.config.service",
        "shared.db.models",
        "shared.db.base",
        "nonebot_plugin_orm",
        *_MONITOR_PLUGIN_MODULES,
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
    from shared.db.models import DynamicMonitorState, LiveMonitorState

    return Model, DynamicMonitorState, LiveMonitorState


def _attach_select_counter(engine) -> tuple[dict[str, int], Callable[[], None]]:
    counter = {"select": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["select"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _before_cursor_execute)

    def cleanup() -> None:
        event.remove(
            engine.sync_engine, "before_cursor_execute", _before_cursor_execute
        )

    return counter, cleanup


@pytest.fixture
async def db_context():
    Model, DynamicMonitorState, LiveMonitorState = _ensure_real_db_modules()

    engine = create_async_engine(_shared_sqlite_url())
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield engine, factory, DynamicMonitorState, LiveMonitorState
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dynamic_load_persisted_states_all_exist(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, _, _ = db_context
    from plugins.dynamic_monitor.config import Config
    from plugins.dynamic_monitor.dynamic_monitor import DynamicMonitor
    from plugins.dynamic_monitor import state_store as dynamic_state_store
    from shared.db.models import DynamicMonitorState

    monkeypatch.setattr(
        dynamic_state_store,
        "get_session",
        lambda: factory(),
    )

    monitor = DynamicMonitor(
        Config(dynamic_monitor_mapping={"111": ["g1"], "222": ["g1"]})
    )

    async with factory() as session:
        async with session.begin():
            session.add(
                DynamicMonitorState(
                    uid="111",
                    last_dynamic_id=100,
                    initialized=True,
                    pinned_dynamic_id=42,
                )
            )
            session.add(
                DynamicMonitorState(
                    uid="222",
                    last_dynamic_id=200,
                    initialized=True,
                    pinned_dynamic_id=99,
                )
            )

    await monitor._load_persisted_states()

    assert monitor.last_dynamic_ids == {"111": 100, "222": 200}
    assert monitor.initialized_uids == {"111": True, "222": True}
    assert monitor.pinned_dynamic_ids == {"111": 42, "222": 99}


@pytest.mark.asyncio
async def test_dynamic_load_persisted_states_none_exist(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory, _, _ = db_context
    from plugins.dynamic_monitor import state_store as dynamic_state_store
    from plugins.dynamic_monitor.config import Config
    from plugins.dynamic_monitor.dynamic_monitor import DynamicMonitor

    monkeypatch.setattr(
        dynamic_state_store,
        "get_session",
        lambda: factory(),
    )

    monitor = DynamicMonitor(
        Config(dynamic_monitor_mapping={"111": ["g1"], "222": ["g1"]})
    )
    await monitor._load_persisted_states()

    assert monitor.last_dynamic_ids == {"111": 0, "222": 0}
    assert monitor.initialized_uids == {"111": False, "222": False}
    assert monitor.pinned_dynamic_ids == {"111": None, "222": None}


@pytest.mark.asyncio
async def test_dynamic_load_persisted_states_partial(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory, _, _ = db_context
    from plugins.dynamic_monitor import state_store as dynamic_state_store
    from plugins.dynamic_monitor.config import Config
    from plugins.dynamic_monitor.dynamic_monitor import DynamicMonitor
    from shared.db.models import DynamicMonitorState

    monkeypatch.setattr(
        dynamic_state_store,
        "get_session",
        lambda: factory(),
    )

    async with factory() as session:
        async with session.begin():
            session.add(
                DynamicMonitorState(
                    uid="111",
                    last_dynamic_id=100,
                    initialized=True,
                    pinned_dynamic_id=42,
                )
            )

    monitor = DynamicMonitor(
        Config(
            dynamic_monitor_mapping={
                "111": ["g1"],
                "222": ["g1"],
                "333": ["g1"],
            }
        )
    )
    await monitor._load_persisted_states()

    assert monitor.last_dynamic_ids["111"] == 100
    assert monitor.initialized_uids["111"] is True
    assert monitor.pinned_dynamic_ids["111"] == 42
    assert monitor.last_dynamic_ids["222"] == 0
    assert monitor.initialized_uids["222"] is False
    assert monitor.pinned_dynamic_ids["222"] is None
    assert monitor.last_dynamic_ids["333"] == 0
    assert monitor.initialized_uids["333"] is False


@pytest.mark.asyncio
async def test_dynamic_load_persisted_states_single_query(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, _, _ = db_context
    from plugins.dynamic_monitor.config import Config
    from plugins.dynamic_monitor.dynamic_monitor import DynamicMonitor
    from plugins.dynamic_monitor import state_store as dynamic_state_store
    from shared.db.models import DynamicMonitorState

    monkeypatch.setattr(
        dynamic_state_store,
        "get_session",
        lambda: factory(),
    )

    uids = [f"{i:03d}" for i in range(120)]
    async with factory() as session:
        async with session.begin():
            for uid in uids:
                session.add(
                    DynamicMonitorState(
                        uid=uid,
                        last_dynamic_id=int(uid),
                        initialized=True,
                    )
                )

    counter, cleanup = _attach_select_counter(engine)
    try:
        monitor = DynamicMonitor(
            Config(dynamic_monitor_mapping={uid: ["g1"] for uid in uids})
        )
        await monitor._load_persisted_states()
    finally:
        cleanup()

    assert counter["select"] == 1
    assert len(monitor.last_dynamic_ids) == 120
    assert monitor.last_dynamic_ids["119"] == 119


@pytest.mark.asyncio
async def test_live_load_persisted_states_all_exist(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, _, _ = db_context
    from plugins.live_monitor.config import Config
    from plugins.live_monitor.live_monitor import LiveMonitor
    from plugins.live_monitor.models import LiveRoomState
    from plugins.live_monitor import state_store as live_state_store
    from shared.db.models import LiveMonitorState

    monkeypatch.setattr(
        live_state_store,
        "get_session",
        lambda: factory(),
    )

    monitor = LiveMonitor(Config(live_monitor_mapping={"111": ["g1"], "222": ["g1"]}))
    monitor.room_states["111"] = LiveRoomState(room_id=111)
    monitor.room_states["222"] = LiveRoomState(room_id=222)

    async with factory() as session:
        async with session.begin():
            session.add(
                LiveMonitorState(
                    room_id="111",
                    previous_status="LIVE",
                    start_time=1000,
                )
            )
            session.add(
                LiveMonitorState(
                    room_id="222",
                    previous_status="PREPARING",
                    start_time=2000,
                )
            )

    await monitor._load_persisted_states()

    assert monitor.room_states["111"].previous_status == LiveStatus.LIVE
    assert monitor.room_states["111"].start_time == 1000
    assert monitor.room_states["222"].previous_status == LiveStatus.PREPARING
    assert monitor.room_states["222"].start_time == 2000


@pytest.mark.asyncio
async def test_live_load_persisted_states_none_exist(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory, _, _ = db_context
    from plugins.live_monitor import state_store as live_state_store
    from plugins.live_monitor.config import Config
    from plugins.live_monitor.live_monitor import LiveMonitor
    from plugins.live_monitor.models import LiveRoomState

    monkeypatch.setattr(
        live_state_store,
        "get_session",
        lambda: factory(),
    )

    monitor = LiveMonitor(Config(live_monitor_mapping={"111": ["g1"], "222": ["g1"]}))
    monitor.room_states["111"] = LiveRoomState(room_id=111)
    monitor.room_states["222"] = LiveRoomState(room_id=222)
    await monitor._load_persisted_states()

    assert monitor.room_states["111"].previous_status == LiveStatus.PREPARING
    assert monitor.room_states["111"].start_time == 0
    assert monitor.room_states["222"].previous_status == LiveStatus.PREPARING


@pytest.mark.asyncio
async def test_live_load_persisted_states_partial(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory, _, _ = db_context
    from plugins.live_monitor import state_store as live_state_store
    from plugins.live_monitor.config import Config
    from plugins.live_monitor.live_monitor import LiveMonitor
    from plugins.live_monitor.models import LiveRoomState
    from shared.db.models import LiveMonitorState

    monkeypatch.setattr(
        live_state_store,
        "get_session",
        lambda: factory(),
    )

    async with factory() as session:
        async with session.begin():
            session.add(
                LiveMonitorState(
                    room_id="111",
                    previous_status="LIVE",
                    start_time=1000,
                )
            )

    monitor = LiveMonitor(
        Config(
            live_monitor_mapping={
                "111": ["g1"],
                "222": ["g1"],
                "333": ["g1"],
            }
        )
    )
    for room_id in ("111", "222", "333"):
        monitor.room_states[room_id] = LiveRoomState(room_id=int(room_id))
    await monitor._load_persisted_states()

    assert monitor.room_states["111"].previous_status == LiveStatus.LIVE
    assert monitor.room_states["111"].start_time == 1000
    assert monitor.room_states["222"].previous_status == LiveStatus.PREPARING
    assert monitor.room_states["222"].start_time == 0
    assert monitor.room_states["333"].previous_status == LiveStatus.PREPARING


@pytest.mark.asyncio
async def test_live_load_persisted_states_single_query(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, _, _ = db_context
    from plugins.live_monitor.config import Config
    from plugins.live_monitor.live_monitor import LiveMonitor
    from plugins.live_monitor.models import LiveRoomState
    from plugins.live_monitor import state_store as live_state_store
    from shared.db.models import LiveMonitorState

    monkeypatch.setattr(
        live_state_store,
        "get_session",
        lambda: factory(),
    )

    room_ids = [f"{i:03d}" for i in range(120)]
    async with factory() as session:
        async with session.begin():
            for room_id in room_ids:
                session.add(
                    LiveMonitorState(
                        room_id=room_id,
                        previous_status="LIVE",
                        start_time=int(room_id),
                    )
                )

    counter, cleanup = _attach_select_counter(engine)
    try:
        monitor = LiveMonitor(
            Config(live_monitor_mapping={room_id: ["g1"] for room_id in room_ids})
        )
        for room_id in room_ids:
            monitor.room_states[room_id] = LiveRoomState(room_id=int(room_id))
        await monitor._load_persisted_states()
    finally:
        cleanup()

    assert counter["select"] == 1
    assert monitor.room_states["119"].start_time == 119
