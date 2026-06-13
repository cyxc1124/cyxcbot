"""Tests for single-shot monitor sync on ConfigService.reload()."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.config.types import AppConfigSnapshot

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"


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
        "plugins",
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
async def test_dynamic_on_config_reload_calls_reload_config_once(dynamic_monitor_mod):
    fake_monitor = MagicMock()
    fake_monitor.reload_config = AsyncMock()
    dynamic_monitor_mod.dynamic_monitor_instance = fake_monitor
    snapshot = AppConfigSnapshot(dynamic_monitor_mapping={"111": ["group1"]})

    await dynamic_monitor_mod._on_config_reload(snapshot)

    fake_monitor.reload_config.assert_awaited_once()


@pytest.mark.asyncio
async def test_dynamic_on_config_reload_starts_when_idle_with_targets(
    dynamic_monitor_mod,
):
    dynamic_monitor_mod.dynamic_monitor_instance = None
    snapshot = AppConfigSnapshot(dynamic_monitor_mapping={"111": ["group1"]})

    with patch.object(
        dynamic_monitor_mod, "start_dynamic_monitor", new_callable=AsyncMock
    ) as start:
        await dynamic_monitor_mod.sync_from_config_reload(snapshot)

    start.assert_awaited_once()


@pytest.mark.asyncio
async def test_dynamic_on_config_reload_stops_when_targets_cleared(
    dynamic_monitor_mod,
):
    fake_monitor = MagicMock()
    fake_monitor.reload_config = AsyncMock()
    dynamic_monitor_mod.dynamic_monitor_instance = fake_monitor
    snapshot = AppConfigSnapshot()

    with patch.object(
        dynamic_monitor_mod, "stop_dynamic_monitor", new_callable=AsyncMock
    ) as stop:
        await dynamic_monitor_mod.sync_from_config_reload(snapshot)

    stop.assert_awaited_once()
    fake_monitor.reload_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_on_config_reload_calls_reload_config_once(live_monitor_mod):
    fake_monitor = MagicMock()
    fake_monitor.reload_config = AsyncMock()
    live_monitor_mod.live_monitor_instance = fake_monitor
    snapshot = AppConfigSnapshot(live_monitor_mapping={"123": ["group1"]})

    await live_monitor_mod._on_config_reload(snapshot)

    fake_monitor.reload_config.assert_awaited_once()


@pytest.mark.asyncio
async def test_dynamic_start_with_no_targets_registers_reload_callback(
    dynamic_monitor_mod,
):
    dynamic_monitor_mod._config_reload_registered = False
    dynamic_monitor_mod.dynamic_monitor_instance = None

    with (
        patch.object(dynamic_monitor_mod, "Config") as config_cls,
        patch.object(
            dynamic_monitor_mod.get_config_service(),
            "register_reload_callback",
        ) as register,
    ):
        config_cls.from_service.return_value = MagicMock(dynamic_monitor_mapping={})
        await dynamic_monitor_mod.start_dynamic_monitor()

    register.assert_called_once_with(dynamic_monitor_mod._on_config_reload)
    dynamic_monitor_mod._config_reload_registered = False


@pytest.mark.asyncio
async def test_config_reload_starts_monitor_after_empty_boot(dynamic_monitor_mod):
    """Bot 无目标启动后，配置热重载添加首个目标应能启动监控。"""
    dynamic_monitor_mod._config_reload_registered = False
    dynamic_monitor_mod.dynamic_monitor_instance = None

    with patch.object(dynamic_monitor_mod, "Config") as config_cls:
        config_cls.from_service.return_value = MagicMock(dynamic_monitor_mapping={})
        await dynamic_monitor_mod.start_dynamic_monitor()

    assert dynamic_monitor_mod._config_reload_registered

    with patch.object(
        dynamic_monitor_mod, "start_dynamic_monitor", new_callable=AsyncMock
    ) as start:
        await dynamic_monitor_mod.sync_from_config_reload(
            AppConfigSnapshot(dynamic_monitor_mapping={"111": ["group1"]})
        )

    start.assert_awaited_once()
    dynamic_monitor_mod._config_reload_registered = False


@pytest.mark.asyncio
async def test_config_service_reload_invokes_monitor_sync_once(dynamic_monitor_mod):
    from shared.config.service import ConfigService

    fake_monitor = MagicMock()
    fake_monitor.reload_config = AsyncMock()
    dynamic_monitor_mod.dynamic_monitor_instance = fake_monitor

    svc = ConfigService.get_instance()
    snapshot = AppConfigSnapshot(dynamic_monitor_mapping={"111": ["group1"]})
    svc._reload_callbacks.clear()
    svc.register_reload_callback(dynamic_monitor_mod._on_config_reload)

    with patch.object(svc, "load", new_callable=AsyncMock, return_value=snapshot):
        await svc.reload()

    fake_monitor.reload_config.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_reload_callback_deduplicates_same_callable():
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()

    callback = AsyncMock()
    unregister_first = svc.register_reload_callback(callback)
    unregister_second = svc.register_reload_callback(callback)

    assert len(svc._reload_callbacks) == 1
    assert unregister_first is not unregister_second

    unregister_first()
    assert len(svc._reload_callbacks) == 0

    unregister_second()
    assert len(svc._reload_callbacks) == 0


@pytest.mark.asyncio
async def test_reload_dispatches_all_callbacks_when_one_unregisters_during_dispatch():
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    snapshot = AppConfigSnapshot()
    invoked: list[str] = []

    async def first_callback(_snapshot):
        invoked.append("first")
        svc.unregister_reload_callback(first_callback)

    async def second_callback(_snapshot):
        invoked.append("second")

    svc.register_reload_callback(first_callback)
    svc.register_reload_callback(second_callback)

    with patch.object(svc, "load", new_callable=AsyncMock, return_value=snapshot):
        await svc.reload()

    assert invoked == ["first", "second"]
    assert len(svc._reload_callbacks) == 1
    assert svc._reload_callbacks[0] is second_callback


@pytest.mark.asyncio
async def test_dynamic_monitor_stop_start_keeps_single_reload_callback(
    dynamic_monitor_mod,
):
    """反复停启监控时，ConfigService 回调列表不应累积。"""
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    dynamic_monitor_mod._config_reload_registered = False
    dynamic_monitor_mod.dynamic_monitor_instance = None

    config = MagicMock(dynamic_monitor_mapping={"111": ["group1"]})
    fake_monitor = AsyncMock()
    fake_monitor.start_monitoring = AsyncMock()
    fake_monitor.stop_monitoring = AsyncMock()

    with (
        patch.object(dynamic_monitor_mod, "Config") as config_cls,
        patch.object(
            dynamic_monitor_mod,
            "DynamicMonitor",
            return_value=fake_monitor,
        ),
    ):
        config_cls.from_service.return_value = config

        for _ in range(3):
            await dynamic_monitor_mod.start_dynamic_monitor()
            assert len(svc._reload_callbacks) == 1
            await dynamic_monitor_mod.stop_dynamic_monitor()
            assert len(svc._reload_callbacks) == 1

    dynamic_monitor_mod._config_reload_registered = False
    dynamic_monitor_mod.dynamic_monitor_instance = None


@pytest.mark.asyncio
async def test_live_monitor_stop_start_keeps_single_reload_callback(
    live_monitor_mod,
):
    """反复停启直播监控时，ConfigService 回调列表不应累积。"""
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    live_monitor_mod._config_reload_registered = False
    live_monitor_mod.live_monitor_instance = None

    config = MagicMock(live_monitor_mapping={"111": ["group1"]})
    fake_monitor = AsyncMock()
    fake_monitor.start_monitoring = AsyncMock()
    fake_monitor.stop_monitoring = AsyncMock()

    with (
        patch.object(live_monitor_mod, "Config") as config_cls,
        patch.object(
            live_monitor_mod,
            "LiveMonitor",
            return_value=fake_monitor,
        ),
    ):
        config_cls.from_service.return_value = config

        for _ in range(3):
            await live_monitor_mod.start_live_monitor()
            assert len(svc._reload_callbacks) == 1
            await live_monitor_mod.stop_live_monitor()
            assert len(svc._reload_callbacks) == 1

    live_monitor_mod._config_reload_registered = False
    live_monitor_mod.live_monitor_instance = None
