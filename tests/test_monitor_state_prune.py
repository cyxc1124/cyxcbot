"""Tests for pruning persisted monitor state when targets are disabled."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import types
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import nonebot
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
DYNAMIC_MONITOR_ROOT = PLUGINS_ROOT / "dynamic_monitor"

_DYNAMIC_MONITOR_MODULE_KEYS = (
    "plugins",
    "plugins.dynamic_monitor",
    "plugins.dynamic_monitor.config",
    "plugins.dynamic_monitor.dynamic_monitor",
    "plugins.dynamic_monitor.sender",
    "nonebot_plugin_apscheduler",
    "utils.screenshot",
)


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
            from shared.db.models import (
                DynamicMonitorState,
                DynamicTarget,
                LiveMonitorState,
                LiveTarget,
            )

            return (
                ConfigService,
                Model,
                DynamicMonitorState,
                DynamicTarget,
                LiveMonitorState,
                LiveTarget,
            )

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
    from shared.db.models import (
        DynamicMonitorState,
        DynamicTarget,
        LiveMonitorState,
        LiveTarget,
    )

    return (
        ConfigService,
        Model,
        DynamicMonitorState,
        DynamicTarget,
        LiveMonitorState,
        LiveTarget,
    )


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


def _load_dynamic_monitor_module(qualified_name: str, filename: str):
    path = DYNAMIC_MONITOR_ROOT / filename
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(DYNAMIC_MONITOR_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _import_dynamic_monitor_modules(
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

    config_mod = _load_dynamic_monitor_module(
        "plugins.dynamic_monitor.config", "config.py"
    )
    monitor_mod = _load_dynamic_monitor_module(
        "plugins.dynamic_monitor.dynamic_monitor", "dynamic_monitor.py"
    )
    monitor_mod.get_session = lambda: session_factory()
    return config_mod.Config, monitor_mod.DynamicMonitor


@pytest.fixture
def dynamic_monitor_plugin_modules() -> Iterator[tuple[Any, Any]]:
    snapshot = {key: sys.modules.get(key) for key in _DYNAMIC_MONITOR_MODULE_KEYS}
    try:
        yield
    finally:
        for key in _DYNAMIC_MONITOR_MODULE_KEYS:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.fixture
async def db_context():
    (
        ConfigService,
        Model,
        DynamicMonitorState,
        DynamicTarget,
        LiveMonitorState,
        LiveTarget,
    ) = _ensure_real_db_modules()

    engine = create_async_engine(_shared_sqlite_url())
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield (
            ConfigService,
            factory,
            DynamicMonitorState,
            DynamicTarget,
            LiveMonitorState,
            LiveTarget,
        )
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
    ConfigService, factory, DynamicMonitorState, DynamicTarget, _, _ = db_context

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
    ConfigService, factory, DynamicMonitorState, DynamicTarget, _, _ = db_context

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
    ConfigService, factory, DynamicMonitorState, DynamicTarget, _, _ = db_context

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


@pytest.mark.asyncio
async def test_dynamic_monitor_reload_config_deletes_persisted_state_from_db(
    db_context: tuple[
        type,
        async_sessionmaker[AsyncSession],
        type,
        type,
    ],
    dynamic_monitor_plugin_modules: None,
) -> None:
    _ConfigService, factory, DynamicMonitorState, _DynamicTarget, _, _ = db_context
    Config, DynamicMonitor = _import_dynamic_monitor_modules(factory)

    monitor = DynamicMonitor(
        Config(dynamic_monitor_mapping={uid: ["group1"] for uid in ["111", "222"]})
    )
    monitor.is_running = True
    for uid in ("111", "222"):
        monitor.last_dynamic_ids[uid] = 100
        monitor.initialized_uids[uid] = True
        monitor.pinned_dynamic_ids[uid] = 42

    async with factory() as session:
        async with session.begin():
            session.add(
                DynamicMonitorState(uid="111", last_dynamic_id=100, initialized=True)
            )
            session.add(
                DynamicMonitorState(uid="222", last_dynamic_id=200, initialized=True)
            )

    reduced_config = Config(
        dynamic_monitor_mapping={"222": ["group1"]},
    )

    with patch(
        "plugins.dynamic_monitor.dynamic_monitor.Config.from_service",
        return_value=reduced_config,
    ):
        await monitor.reload_config()

    async with factory() as session:
        removed = await session.get(DynamicMonitorState, "111")
        kept = await session.get(DynamicMonitorState, "222")

    assert removed is None
    assert kept is not None
    assert kept.last_dynamic_id == 200
    assert kept.initialized is True


@pytest.mark.asyncio
async def test_config_load_prunes_disabled_live_monitor_state(
    db_context: tuple[
        type,
        async_sessionmaker[AsyncSession],
        type,
        type,
        type,
        type,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ConfigService, factory, _, _, LiveMonitorState, LiveTarget = db_context

    async with factory() as session:
        async with session.begin():
            session.add(LiveTarget(room_id="111", enabled=True))
            session.add(LiveTarget(room_id="222", enabled=False))
            session.add(
                LiveMonitorState(
                    room_id="111",
                    previous_status="live",
                    start_time=1000,
                    streamer_name="A",
                )
            )
            session.add(
                LiveMonitorState(
                    room_id="222",
                    previous_status="offline",
                    start_time=2000,
                    streamer_name="B",
                )
            )

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )

    service = ConfigService()
    await service.load()

    async with factory() as session:
        active = await session.get(LiveMonitorState, "111")
        removed = await session.get(LiveMonitorState, "222")

    assert active is not None
    assert active.previous_status == "live"
    assert removed is None


@pytest.mark.asyncio
async def test_config_load_prunes_orphaned_live_monitor_state(
    db_context: tuple[
        type,
        async_sessionmaker[AsyncSession],
        type,
        type,
        type,
        type,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State for a deleted target (no LiveTarget row) should be removed."""
    ConfigService, factory, _, _, LiveMonitorState, LiveTarget = db_context

    async with factory() as session:
        async with session.begin():
            session.add(LiveTarget(room_id="111", enabled=True))
            session.add(
                LiveMonitorState(
                    room_id="111",
                    previous_status="live",
                    start_time=1000,
                    streamer_name="A",
                )
            )
            session.add(
                LiveMonitorState(
                    room_id="999",
                    previous_status="offline",
                    start_time=9000,
                    streamer_name="Orphan",
                )
            )

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )

    service = ConfigService()
    await service.load()

    async with factory() as session:
        active = await session.get(LiveMonitorState, "111")
        orphaned = await session.get(LiveMonitorState, "999")

    assert active is not None
    assert orphaned is None


@pytest.mark.asyncio
async def test_config_load_prunes_all_live_states_when_no_enabled_targets(
    db_context: tuple[
        type,
        async_sessionmaker[AsyncSession],
        type,
        type,
        type,
        type,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every live target is disabled, all persisted states should be cleared."""
    ConfigService, factory, _, _, LiveMonitorState, LiveTarget = db_context

    async with factory() as session:
        async with session.begin():
            session.add(LiveTarget(room_id="111", enabled=False))
            session.add(LiveTarget(room_id="222", enabled=False))
            session.add(
                LiveMonitorState(
                    room_id="111",
                    previous_status="live",
                    start_time=1000,
                    streamer_name="A",
                )
            )
            session.add(
                LiveMonitorState(
                    room_id="222",
                    previous_status="offline",
                    start_time=2000,
                    streamer_name="B",
                )
            )

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )

    service = ConfigService()
    await service.load()

    async with factory() as session:
        state_111 = await session.get(LiveMonitorState, "111")
        state_222 = await session.get(LiveMonitorState, "222")

    assert state_111 is None
    assert state_222 is None
