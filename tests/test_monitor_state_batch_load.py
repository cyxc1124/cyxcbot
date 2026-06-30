"""Tests for batch-loading persisted monitor state (issue #87)."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import types
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from utils.bilibili_api import LiveStatus

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
DYNAMIC_MONITOR_ROOT = PLUGINS_ROOT / "dynamic_monitor"
LIVE_MONITOR_ROOT = PLUGINS_ROOT / "live_monitor"

_DYNAMIC_MODULE_KEYS = (
    "plugins",
    "plugins.dynamic_monitor",
    "plugins.dynamic_monitor.config",
    "plugins.dynamic_monitor.dynamic_monitor",
    "plugins.dynamic_monitor.sender",
    "nonebot_plugin_apscheduler",
    "utils.screenshot",
)

_LIVE_MODULE_KEYS = (
    "plugins",
    "plugins.live_monitor",
    "plugins.live_monitor.models",
    "plugins.live_monitor.config",
    "plugins.live_monitor.live_monitor",
    "plugins.live_monitor.danmaku_client",
    "plugins.live_monitor.card_generator",
    "plugins.live_monitor.sender",
    "nonebot_plugin_apscheduler",
)


def _shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


def _ensure_real_db_modules():
    existing = sys.modules.get("shared.db.models")
    if existing is not None and not isinstance(existing, MagicMock):
        user = getattr(existing, "User", None)
        if user is not None and not isinstance(user, MagicMock):
            from shared.db.base import Model
            from shared.db.models import DynamicMonitorState, LiveMonitorState

            return Model, DynamicMonitorState, LiveMonitorState

    for name in ("shared.db.models", "shared.db.base", "nonebot_plugin_orm"):
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

    import shared.db.base  # noqa: F401 — register ORM metadata
    from shared.db.base import Model
    from shared.db.models import DynamicMonitorState, LiveMonitorState

    return Model, DynamicMonitorState, LiveMonitorState


def _ensure_package(name: str, path: Path) -> types.ModuleType:
    if name in sys.modules:
        module = sys.modules[name]
        if not getattr(module, "__path__", None):
            module.__path__ = [str(path)]
        return module
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


def _load_module(root: Path, qualified_name: str, filename: str):
    path = root / filename
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(root)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _import_dynamic_monitor(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[Any, Any]:
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.dynamic_monitor", DYNAMIC_MONITOR_ROOT)

    sys.modules["nonebot_plugin_apscheduler"] = MagicMock(scheduler=MagicMock())
    sys.modules["plugins.dynamic_monitor.sender"] = MagicMock(
        DynamicSender=MagicMock(),
    )
    sys.modules["utils.screenshot"] = MagicMock(
        init_screenshot_service=AsyncMock(),
        close_screenshot_service=AsyncMock(),
        get_dynamic_screenshot=AsyncMock(),
    )

    config_mod = _load_module(
        DYNAMIC_MONITOR_ROOT, "plugins.dynamic_monitor.config", "config.py"
    )
    monitor_mod = _load_module(
        DYNAMIC_MONITOR_ROOT,
        "plugins.dynamic_monitor.dynamic_monitor",
        "dynamic_monitor.py",
    )
    monitor_mod.get_session = lambda: session_factory()
    return config_mod.Config, monitor_mod.DynamicMonitor


def _import_live_monitor(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[Any, Any, Any]:
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", LIVE_MONITOR_ROOT)

    sys.modules["nonebot_plugin_apscheduler"] = MagicMock(scheduler=MagicMock())
    sys.modules["plugins.live_monitor.danmaku_client"] = MagicMock(
        DanmakuClient=MagicMock(),
    )
    sys.modules["plugins.live_monitor.card_generator"] = MagicMock(
        PrefetchImages=MagicMock(),
        prefetch_card_images=AsyncMock(),
    )
    sys.modules["plugins.live_monitor.sender"] = MagicMock(
        LiveNotificationSender=MagicMock(),
    )

    models_mod = _load_module(
        LIVE_MONITOR_ROOT, "plugins.live_monitor.models", "models.py"
    )
    config_mod = _load_module(
        LIVE_MONITOR_ROOT, "plugins.live_monitor.config", "config.py"
    )
    monitor_mod = _load_module(
        LIVE_MONITOR_ROOT,
        "plugins.live_monitor.live_monitor",
        "live_monitor.py",
    )
    monitor_mod.get_session = lambda: session_factory()
    return config_mod.Config, monitor_mod.LiveMonitor, models_mod.LiveRoomState


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


@pytest.fixture
def dynamic_monitor_modules(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
) -> Iterator[tuple[Any, Any]]:
    _, factory, _, _ = db_context
    snapshot = {key: sys.modules.get(key) for key in _DYNAMIC_MODULE_KEYS}
    try:
        yield _import_dynamic_monitor(factory)
    finally:
        for key in _DYNAMIC_MODULE_KEYS:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.fixture
def live_monitor_modules(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
) -> Iterator[tuple[Any, Any, Any]]:
    _, factory, _, _ = db_context
    snapshot = {key: sys.modules.get(key) for key in _LIVE_MODULE_KEYS}
    try:
        yield _import_live_monitor(factory)
    finally:
        for key in _LIVE_MODULE_KEYS:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.mark.asyncio
async def test_dynamic_load_persisted_states_all_exist(
    db_context: tuple[Any, async_sessionmaker[AsyncSession], type, type],
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    _, factory, DynamicMonitorState, _ = db_context
    Config, DynamicMonitor = dynamic_monitor_modules

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

    monitor = DynamicMonitor(
        Config(dynamic_monitor_mapping={"111": ["g1"], "222": ["g1"]})
    )
    await monitor._load_persisted_states()

    assert monitor.last_dynamic_ids == {"111": 100, "222": 200}
    assert monitor.initialized_uids == {"111": True, "222": True}
    assert monitor.pinned_dynamic_ids == {"111": 42, "222": 99}


@pytest.mark.asyncio
async def test_dynamic_load_persisted_states_none_exist(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    Config, DynamicMonitor = dynamic_monitor_modules

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
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    _, factory, DynamicMonitorState, _ = db_context
    Config, DynamicMonitor = dynamic_monitor_modules

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
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    engine, factory, DynamicMonitorState, _ = db_context
    Config, DynamicMonitor = dynamic_monitor_modules

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
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    _, factory, _, LiveMonitorState = db_context
    Config, LiveMonitor, LiveRoomState = live_monitor_modules

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

    monitor = LiveMonitor(Config(live_monitor_mapping={"111": ["g1"], "222": ["g1"]}))
    monitor.room_states["111"] = LiveRoomState(room_id=111)
    monitor.room_states["222"] = LiveRoomState(room_id=222)
    await monitor._load_persisted_states()

    assert monitor.room_states["111"].previous_status == LiveStatus.LIVE
    assert monitor.room_states["111"].start_time == 1000
    assert monitor.room_states["222"].previous_status == LiveStatus.PREPARING
    assert monitor.room_states["222"].start_time == 2000


@pytest.mark.asyncio
async def test_live_load_persisted_states_none_exist(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules

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
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    _, factory, _, LiveMonitorState = db_context
    Config, LiveMonitor, LiveRoomState = live_monitor_modules

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
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    engine, factory, _, LiveMonitorState = db_context
    Config, LiveMonitor, LiveRoomState = live_monitor_modules

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
