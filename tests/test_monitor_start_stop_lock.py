"""Tests for monitor start/stop lifecycle locking."""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PLUGINS_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1] / "plugins"


@pytest.fixture
def dynamic_monitor_mod():
    sys.path.insert(0, str(PLUGINS_ROOT.parent))
    import plugins.dynamic_monitor.dynamic_monitor as monitor_mod

    monitor_mod._config_reload_registered = False
    monitor_mod.dynamic_monitor_instance = None
    yield monitor_mod
    monitor_mod._config_reload_registered = False
    monitor_mod.dynamic_monitor_instance = None


@pytest.fixture
def live_monitor_mod():
    sys.path.insert(0, str(PLUGINS_ROOT.parent))
    import plugins.live_monitor.live_monitor as monitor_mod

    monitor_mod._config_reload_registered = False
    monitor_mod.live_monitor_instance = None
    yield monitor_mod
    monitor_mod._config_reload_registered = False
    monitor_mod.live_monitor_instance = None


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
