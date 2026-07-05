"""Tests for monitor start/stop lifecycle locking."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"


# 与 test_config_reload_monitors.py 保持一致：通过 importlib 按文件路径加载插件模块并
# mock 掉重量级依赖（nonebot_plugin_orm 等），避免走正常 import 触发插件包 __init__（会
# 注册 on_bot_connect 等事件）并把真实 state_store/DB 模块残留进 sys.modules，污染同一
# pytest 进程内其他测试文件（例如 test_monitor_state_batch_load.py）。


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


def _load_dynamic_monitor_module():
    plugin_root = PLUGINS_ROOT / "dynamic_monitor"
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.dynamic_monitor", plugin_root)
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
    path = plugin_root / "dynamic_monitor.py"
    spec = importlib.util.spec_from_file_location(
        "plugins.dynamic_monitor.dynamic_monitor",
        path,
        submodule_search_locations=[str(plugin_root)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["plugins.dynamic_monitor.dynamic_monitor"] = module
    spec.loader.exec_module(module)
    return module


def _load_live_monitor_module():
    plugin_root = PLUGINS_ROOT / "live_monitor"
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", plugin_root)
    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock()),
    )
    sys.modules.setdefault(
        "plugins.live_monitor.card_generator",
        MagicMock(prefetch_card_images=AsyncMock(), PrefetchImages=MagicMock()),
    )
    sys.modules.setdefault(
        "plugins.live_monitor.danmaku_client",
        MagicMock(DanmakuClient=MagicMock()),
    )
    sys.modules.setdefault(
        "plugins.live_monitor.sender",
        MagicMock(LiveNotificationSender=MagicMock()),
    )
    path = plugin_root / "live_monitor.py"
    spec = importlib.util.spec_from_file_location(
        "plugins.live_monitor.live_monitor",
        path,
        submodule_search_locations=[str(plugin_root)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["plugins.live_monitor.live_monitor"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dynamic_monitor_mod():
    keys = (
        "plugins.dynamic_monitor.dynamic_monitor",
        "plugins.dynamic_monitor",
        "nonebot_plugin_apscheduler",
        "nonebot_plugin_orm",
        "utils.screenshot",
        "plugins.dynamic_monitor.sender",
    )
    snapshot = {key: sys.modules.get(key) for key in keys}
    mod = _load_dynamic_monitor_module()
    mod.dynamic_monitor_instance = None
    try:
        yield mod
    finally:
        mod.dynamic_monitor_instance = None
        for key in keys:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.fixture
def live_monitor_mod():
    keys = (
        "plugins.live_monitor.live_monitor",
        "plugins.live_monitor",
        "nonebot_plugin_apscheduler",
        "nonebot_plugin_orm",
        "plugins.live_monitor.card_generator",
        "plugins.live_monitor.danmaku_client",
        "plugins.live_monitor.sender",
    )
    snapshot = {key: sys.modules.get(key) for key in keys}
    mod = _load_live_monitor_module()
    mod.live_monitor_instance = None
    try:
        yield mod
    finally:
        mod.live_monitor_instance = None
        for key in keys:
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
