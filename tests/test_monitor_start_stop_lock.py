"""Tests for monitor start/stop lifecycle locking."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
DYNAMIC_ROOT = PLUGINS_ROOT / "dynamic_monitor"
LIVE_ROOT = PLUGINS_ROOT / "live_monitor"

_DYNAMIC_TOUCHED = (
    "plugins",
    "plugins.dynamic_monitor",
    "plugins.dynamic_monitor.config",
    "plugins.dynamic_monitor.dynamic_monitor",
    "plugins.dynamic_monitor.sender",
    "nonebot_plugin_apscheduler",
    "nonebot_plugin_orm",
    "utils.screenshot",
)
_LIVE_TOUCHED = (
    "plugins",
    "plugins.live_monitor",
    "plugins.live_monitor.models",
    "plugins.live_monitor.config",
    "plugins.live_monitor.live_monitor",
    "plugins.live_monitor.danmaku_client",
    "plugins.live_monitor.card_generator",
    "plugins.live_monitor.sender",
    "nonebot_plugin_apscheduler",
    "nonebot_plugin_orm",
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


def _load_module(plugin_root: Path, qualified_name: str, filename: str):
    path = plugin_root / filename
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(plugin_root)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _import_dynamic_monitor_mod():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.dynamic_monitor", DYNAMIC_ROOT)
    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock()),
    )
    sys.modules.setdefault(
        "plugins.dynamic_monitor.sender",
        MagicMock(DynamicSender=MagicMock()),
    )
    sys.modules.setdefault(
        "utils.screenshot",
        MagicMock(
            init_screenshot_service=AsyncMock(),
            close_screenshot_service=AsyncMock(),
            get_dynamic_screenshot=AsyncMock(),
        ),
    )
    _load_module(DYNAMIC_ROOT, "plugins.dynamic_monitor.config", "config.py")
    return _load_module(
        DYNAMIC_ROOT,
        "plugins.dynamic_monitor.dynamic_monitor",
        "dynamic_monitor.py",
    )


def _import_live_monitor_mod():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", LIVE_ROOT)
    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    db_session = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=db_session)
    tx.__aexit__ = AsyncMock(return_value=None)
    db_session.begin = MagicMock(return_value=tx)
    db_session.get = AsyncMock(return_value=None)
    db_session.delete = AsyncMock()
    db_session.add = MagicMock()
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock(return_value=db_session)),
    )
    sys.modules.setdefault(
        "plugins.live_monitor.danmaku_client",
        MagicMock(DanmakuClient=MagicMock()),
    )
    sys.modules.setdefault(
        "plugins.live_monitor.card_generator",
        MagicMock(
            PrefetchImages=MagicMock(),
            prefetch_card_images=AsyncMock(),
        ),
    )
    sys.modules.setdefault(
        "plugins.live_monitor.sender",
        MagicMock(LiveNotificationSender=MagicMock()),
    )
    _load_module(LIVE_ROOT, "plugins.live_monitor.models", "models.py")
    _load_module(LIVE_ROOT, "plugins.live_monitor.config", "config.py")
    return _load_module(
        LIVE_ROOT,
        "plugins.live_monitor.live_monitor",
        "live_monitor.py",
    )


@pytest.fixture
def dynamic_monitor_mod() -> Iterator[Any]:
    snapshot = {key: sys.modules.get(key) for key in _DYNAMIC_TOUCHED}
    try:
        mod = _import_dynamic_monitor_mod()
        mod._config_reload_registered = False
        mod.dynamic_monitor_instance = None
        yield mod
    finally:
        for key in _DYNAMIC_TOUCHED:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.fixture
def live_monitor_mod() -> Iterator[Any]:
    snapshot = {key: sys.modules.get(key) for key in _LIVE_TOUCHED}
    try:
        mod = _import_live_monitor_mod()
        mod._config_reload_registered = False
        mod.live_monitor_instance = None
        yield mod
    finally:
        for key in _LIVE_TOUCHED:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.mark.asyncio
async def test_start_dynamic_monitor_waits_for_in_flight_stop(
    dynamic_monitor_mod,
) -> None:
    """Bot 重连时 start 应等待 stop 完成并重建监控，而非误判已在运行。"""
    stop_started = asyncio.Event()
    stop_release = asyncio.Event()
    start_monitoring = AsyncMock()

    class StoppingMonitor:
        is_running = True

        async def stop_monitoring(self) -> None:
            self.is_running = False
            stop_started.set()
            await stop_release.wait()

    stale = StoppingMonitor()
    dynamic_monitor_mod.dynamic_monitor_instance = stale

    config = SimpleNamespace(
        dynamic_monitor_mapping={"123": ["1001"]},
        dynamic_monitor_user_mapping={},
        monitor_interval=60,
    )
    replacement = MagicMock()
    replacement.start_monitoring = start_monitoring
    replacement.is_running = False

    stop_task = asyncio.create_task(dynamic_monitor_mod.stop_dynamic_monitor())
    await stop_started.wait()

    with (
        patch.object(dynamic_monitor_mod, "Config") as config_cls,
        patch.object(dynamic_monitor_mod, "DynamicMonitor", return_value=replacement),
    ):
        config_cls.from_service.return_value = config
        start_task = asyncio.create_task(dynamic_monitor_mod.start_dynamic_monitor())
        await asyncio.sleep(0.05)
        assert dynamic_monitor_mod.dynamic_monitor_instance is stale
        stop_release.set()
        await asyncio.gather(stop_task, start_task)

    assert dynamic_monitor_mod.dynamic_monitor_instance is replacement
    start_monitoring.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_live_monitor_waits_for_in_flight_stop(live_monitor_mod) -> None:
    stop_started = asyncio.Event()
    stop_release = asyncio.Event()
    start_monitoring = AsyncMock()

    class StoppingMonitor:
        is_running = True

        async def stop_monitoring(self) -> None:
            self.is_running = False
            stop_started.set()
            await stop_release.wait()

    stale = StoppingMonitor()
    live_monitor_mod.live_monitor_instance = stale

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        monitor_interval=60,
        use_websocket=False,
    )
    replacement = MagicMock()
    replacement.start_monitoring = start_monitoring
    replacement.is_running = False

    stop_task = asyncio.create_task(live_monitor_mod.stop_live_monitor())
    await stop_started.wait()

    with (
        patch.object(live_monitor_mod, "Config") as config_cls,
        patch.object(live_monitor_mod, "LiveMonitor", return_value=replacement),
    ):
        config_cls.from_service.return_value = config
        start_task = asyncio.create_task(live_monitor_mod.start_live_monitor())
        await asyncio.sleep(0.05)
        assert live_monitor_mod.live_monitor_instance is stale
        stop_release.set()
        await asyncio.gather(stop_task, start_task)

    assert live_monitor_mod.live_monitor_instance is replacement
    start_monitoring.assert_awaited_once()
