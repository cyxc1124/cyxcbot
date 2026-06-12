"""Tests for live monitor config hot reload."""

from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
PLUGIN_ROOT = PLUGINS_ROOT / "live_monitor"

_TOUCHED_MODULE_KEYS = (
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


def _load_module(qualified_name: str, filename: str):
    path = PLUGIN_ROOT / filename
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _import_live_monitor_modules():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", PLUGIN_ROOT)

    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock()),
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

    models_mod = _load_module("plugins.live_monitor.models", "models.py")
    config_mod = _load_module("plugins.live_monitor.config", "config.py")
    monitor_mod = _load_module("plugins.live_monitor.live_monitor", "live_monitor.py")
    return config_mod.Config, monitor_mod.LiveMonitor, models_mod.LiveRoomState


@pytest.fixture
def live_monitor_modules() -> Iterator[tuple[Any, Any, Any]]:
    snapshot = {key: sys.modules.get(key) for key in _TOUCHED_MODULE_KEYS}
    try:
        yield _import_live_monitor_modules()
    finally:
        for key in _TOUCHED_MODULE_KEYS:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


def _make_monitor(
    Config: Any,
    LiveMonitor: Any,
    LiveRoomState: Any,
    room_ids: list[str],
):
    config = Config(
        live_monitor_mapping={room_id: ["group1"] for room_id in room_ids},
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    monitor.is_running = True
    for room_id in room_ids:
        monitor.room_states[room_id] = LiveRoomState(room_id=int(room_id))
        monitor.initialized_rooms[room_id] = True
    return monitor


@pytest.mark.asyncio
async def test_reload_config_removes_deleted_room_state_and_websocket(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111", "222"])
    removed_client = AsyncMock()
    monitor._danmaku_clients["111"] = removed_client
    monitor._danmaku_clients["222"] = AsyncMock()

    reduced_config = Config(
        live_monitor_mapping={"222": ["group1"]},
        use_websocket=True,
    )

    with (
        patch(
            "plugins.live_monitor.live_monitor.Config.from_service",
            return_value=reduced_config,
        ),
        patch(
            "plugins.live_monitor.live_monitor.api_manager.init",
            new_callable=AsyncMock,
        ),
    ):
        await monitor.reload_config()

    assert "111" not in monitor.room_states
    assert "111" not in monitor.initialized_rooms
    assert "111" not in monitor._danmaku_clients
    removed_client.stop.assert_awaited_once()
    assert "222" in monitor.room_states
    assert "222" in monitor._danmaku_clients


@pytest.mark.asyncio
async def test_check_all_rooms_only_polls_configured_targets(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["222"])
    monitor.room_states["999"] = LiveRoomState(room_id=999)
    monitor.initialized_rooms["999"] = True

    checked: list[str] = []

    async def fake_check(room_id: str) -> bool:
        checked.append(room_id)
        return True

    monitor._check_room_status = fake_check  # type: ignore[method-assign]
    monitor._cycle_logger.emit_summary = lambda: None  # type: ignore[method-assign]

    await monitor._check_all_rooms()

    assert checked == ["222"]


@pytest.mark.asyncio
async def test_reload_config_restarts_websocket_clients_when_cookie_changes(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111", "222"])
    monitor.config.bilibili_cookie = None
    old_client_111 = AsyncMock()
    old_client_222 = AsyncMock()
    monitor._danmaku_clients["111"] = old_client_111
    monitor._danmaku_clients["222"] = old_client_222

    updated_config = Config(
        live_monitor_mapping={"111": ["group1"], "222": ["group1"]},
        use_websocket=True,
        bilibili_cookie="DedeUserID=123; buvid3=abc",
    )

    with (
        patch(
            "plugins.live_monitor.live_monitor.Config.from_service",
            return_value=updated_config,
        ),
        patch(
            "plugins.live_monitor.live_monitor.api_manager.init",
            new_callable=AsyncMock,
        ),
        patch.object(
            monitor,
            "_start_single_danmaku_client",
            new_callable=AsyncMock,
        ) as start_client,
    ):
        await monitor.reload_config()

    old_client_111.stop.assert_awaited_once()
    old_client_222.stop.assert_awaited_once()
    assert start_client.await_count == 2
    start_client.assert_any_await("111")
    start_client.assert_any_await("222")


@pytest.mark.asyncio
async def test_reload_config_keeps_websocket_clients_when_cookie_unchanged(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])
    cookie = "DedeUserID=123; buvid3=abc"
    monitor.config.bilibili_cookie = cookie
    existing_client = AsyncMock()
    monitor._danmaku_clients["111"] = existing_client

    unchanged_config = Config(
        live_monitor_mapping={"111": ["group1"]},
        use_websocket=True,
        bilibili_cookie=cookie,
    )

    with (
        patch(
            "plugins.live_monitor.live_monitor.Config.from_service",
            return_value=unchanged_config,
        ),
        patch(
            "plugins.live_monitor.live_monitor.api_manager.init",
            new_callable=AsyncMock,
        ),
        patch.object(
            monitor,
            "_restart_single_danmaku_client",
            new_callable=AsyncMock,
        ) as restart_client,
    ):
        await monitor.reload_config()

    existing_client.stop.assert_not_awaited()
    restart_client.assert_not_awaited()
    assert monitor._danmaku_clients["111"] is existing_client


@pytest.mark.asyncio
async def test_reload_config_continues_cookie_reload_when_one_room_fails(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111", "222"])
    monitor.config.bilibili_cookie = None
    monitor._danmaku_clients["111"] = AsyncMock()
    monitor._danmaku_clients["222"] = AsyncMock()

    updated_config = Config(
        live_monitor_mapping={"111": ["group1"], "222": ["group1"]},
        use_websocket=True,
        bilibili_cookie="DedeUserID=123; buvid3=abc",
    )

    async def restart_side_effect(room_id: str) -> None:
        if room_id == "111":
            raise ConnectionError("websocket reconnect failed")

    with (
        patch(
            "plugins.live_monitor.live_monitor.Config.from_service",
            return_value=updated_config,
        ),
        patch(
            "plugins.live_monitor.live_monitor.api_manager.init",
            new_callable=AsyncMock,
        ),
        patch.object(
            monitor,
            "_restart_single_danmaku_client",
            side_effect=restart_side_effect,
        ) as restart_client,
    ):
        await monitor.reload_config()

    assert restart_client.await_count == 2
    restart_client.assert_any_await("111")
    restart_client.assert_any_await("222")


@pytest.mark.asyncio
async def test_start_single_danmaku_client_removes_failed_client_from_registry(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])

    failed_client = AsyncMock()
    failed_client.start = AsyncMock(side_effect=ConnectionError("start failed"))

    with (
        patch(
            "plugins.live_monitor.live_monitor.DanmakuClient",
            return_value=failed_client,
        ),
        pytest.raises(ConnectionError, match="start failed"),
    ):
        await monitor._start_single_danmaku_client("111")

    assert "111" not in monitor._danmaku_clients


@pytest.mark.asyncio
async def test_start_single_danmaku_client_can_retry_after_start_failure(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])

    failed_client = AsyncMock()
    failed_client.start = AsyncMock(side_effect=ConnectionError("start failed"))
    success_client = AsyncMock()

    with patch(
        "plugins.live_monitor.live_monitor.DanmakuClient",
        side_effect=[failed_client, success_client],
    ):
        with pytest.raises(ConnectionError):
            await monitor._start_single_danmaku_client("111")
        await monitor._start_single_danmaku_client("111")

    assert monitor._danmaku_clients["111"] is success_client
    success_client.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_reload_config_restarts_websocket_clients_on_logout(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])
    monitor.config.bilibili_cookie = "DedeUserID=123; buvid3=abc"
    old_client = AsyncMock()
    monitor._danmaku_clients["111"] = old_client

    logged_out_config = Config(
        live_monitor_mapping={"111": ["group1"]},
        use_websocket=True,
        bilibili_cookie=None,
    )

    with (
        patch(
            "plugins.live_monitor.live_monitor.Config.from_service",
            return_value=logged_out_config,
        ),
        patch(
            "plugins.live_monitor.live_monitor.api_manager.init",
            new_callable=AsyncMock,
        ),
        patch.object(
            monitor,
            "_start_single_danmaku_client",
            new_callable=AsyncMock,
        ) as start_client,
    ):
        await monitor.reload_config()

    old_client.stop.assert_awaited_once()
    start_client.assert_awaited_once_with("111")


def test_plugins_package_available_after_live_monitor_tests() -> None:
    import importlib

    plugins = importlib.import_module("plugins")
    assert getattr(plugins, "__path__", None)

    spec = importlib.util.find_spec("plugins.video_monitor")
    assert spec is not None
