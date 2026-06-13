"""Tests for live monitor config hot reload."""

from __future__ import annotations

import asyncio
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
async def test_reload_config_cookie_reload_before_new_room_start(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])
    monitor.config.bilibili_cookie = None
    monitor._danmaku_clients["111"] = AsyncMock()

    updated_config = Config(
        live_monitor_mapping={"111": ["group1"], "333": ["group1"]},
        use_websocket=True,
        bilibili_cookie="DedeUserID=123; buvid3=abc",
    )
    call_order: list[tuple[str, str]] = []

    async def track_restart(room_id: str) -> None:
        call_order.append(("restart", room_id))

    async def track_start(room_id: str) -> None:
        call_order.append(("start", room_id))

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
            side_effect=track_restart,
        ),
        patch.object(
            monitor,
            "_start_single_danmaku_client",
            side_effect=track_start,
        ),
    ):
        await monitor.reload_config()

    assert call_order == [("restart", "111"), ("start", "333")]


@pytest.mark.asyncio
async def test_reload_config_cookie_reload_continues_when_new_room_start_fails(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])
    monitor.config.bilibili_cookie = None
    old_client = AsyncMock()
    monitor._danmaku_clients["111"] = old_client

    updated_config = Config(
        live_monitor_mapping={"111": ["group1"], "333": ["group1"]},
        use_websocket=True,
        bilibili_cookie="DedeUserID=123; buvid3=abc",
    )

    async def start_side_effect(room_id: str) -> None:
        if room_id == "333":
            raise ConnectionError("new room start failed")

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
            new_callable=AsyncMock,
        ) as restart_client,
        patch.object(
            monitor,
            "_start_single_danmaku_client",
            side_effect=start_side_effect,
        ) as start_client,
    ):
        await monitor.reload_config()

    restart_client.assert_awaited_once_with("111")
    start_client.assert_awaited_once_with("333")


@pytest.mark.asyncio
async def test_reload_config_continues_when_one_room_removal_fails(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111", "222"])

    reduced_config = Config(
        live_monitor_mapping={"222": ["group1"]},
        use_websocket=True,
    )

    async def remove_side_effect(room_id: str) -> None:
        if room_id == "111":
            raise RuntimeError("remove failed")

    with (
        patch(
            "plugins.live_monitor.live_monitor.Config.from_service",
            return_value=reduced_config,
        ),
        patch(
            "plugins.live_monitor.live_monitor.api_manager.init",
            new_callable=AsyncMock,
        ),
        patch.object(
            monitor,
            "_remove_room",
            side_effect=remove_side_effect,
        ) as remove_room,
    ):
        await monitor.reload_config()

    assert remove_room.await_count == 1
    assert "222" in monitor.room_states


@pytest.mark.asyncio
async def test_restart_single_danmaku_client_preserves_old_client_on_start_failure(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])
    old_client = AsyncMock()
    monitor._danmaku_clients["111"] = old_client

    with (
        patch.object(
            monitor,
            "_start_single_danmaku_client",
            AsyncMock(side_effect=ConnectionError("start failed")),
        ),
        pytest.raises(ConnectionError, match="start failed"),
    ):
        await monitor._restart_single_danmaku_client("111")

    assert monitor._danmaku_clients["111"] is old_client
    old_client.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_single_danmaku_client_stops_old_client_after_successful_start(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])
    old_client = AsyncMock()
    new_client = AsyncMock()
    monitor._danmaku_clients["111"] = old_client

    async def fake_start(room_id: str) -> None:
        monitor._danmaku_clients[room_id] = new_client

    with patch.object(
        monitor,
        "_start_single_danmaku_client",
        side_effect=fake_start,
    ):
        await monitor._restart_single_danmaku_client("111")

    old_client.stop.assert_awaited_once()
    assert monitor._danmaku_clients["111"] is new_client


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
async def test_start_single_danmaku_client_blocks_concurrent_start_while_in_flight(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])

    start_gate = asyncio.Event()
    in_flight_client = AsyncMock()

    async def slow_start() -> None:
        start_gate.set()
        await asyncio.sleep(0.05)

    in_flight_client.start = slow_start
    duplicate_client = AsyncMock()

    with patch(
        "plugins.live_monitor.live_monitor.DanmakuClient",
        side_effect=[in_flight_client, duplicate_client],
    ) as create_client:
        first_task = asyncio.create_task(monitor._start_single_danmaku_client("111"))
        await start_gate.wait()
        await monitor._start_single_danmaku_client("111")
        await first_task

    create_client.assert_called_once()
    duplicate_client.start.assert_not_awaited()
    assert monitor._danmaku_clients["111"] is in_flight_client


@pytest.mark.asyncio
async def test_stale_start_failure_does_not_remove_replacement_client(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])

    stale_start_gate = asyncio.Event()
    stale_client = AsyncMock()
    replacement_client = AsyncMock()

    async def slow_then_fail() -> None:
        stale_start_gate.set()
        await asyncio.sleep(0.05)
        raise ConnectionError("stale start failed")

    stale_client.start = slow_then_fail

    with patch(
        "plugins.live_monitor.live_monitor.DanmakuClient",
        side_effect=[stale_client, replacement_client],
    ):
        stale_task = asyncio.create_task(monitor._start_single_danmaku_client("111"))
        await stale_start_gate.wait()
        await monitor._restart_single_danmaku_client("111")
        with pytest.raises(ConnectionError, match="stale start failed"):
            await stale_task

    assert monitor._danmaku_clients["111"] is replacement_client
    replacement_client.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_stale_start_failure_does_not_remove_restored_client_after_restart_failure(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])

    stale_start_gate = asyncio.Event()
    stale_client = AsyncMock()
    failed_replacement_client = AsyncMock()

    async def slow_then_fail() -> None:
        stale_start_gate.set()
        await asyncio.sleep(0.05)
        raise ConnectionError("stale start failed")

    async def replacement_fail() -> None:
        raise ConnectionError("replacement start failed")

    stale_client.start = slow_then_fail
    failed_replacement_client.start = replacement_fail

    with patch(
        "plugins.live_monitor.live_monitor.DanmakuClient",
        side_effect=[stale_client, failed_replacement_client],
    ):
        stale_task = asyncio.create_task(monitor._start_single_danmaku_client("111"))
        await stale_start_gate.wait()
        with pytest.raises(ConnectionError, match="replacement start failed"):
            await monitor._restart_single_danmaku_client("111")
        with pytest.raises(ConnectionError, match="stale start failed"):
            await stale_task

    assert monitor._danmaku_clients["111"] is stale_client


@pytest.mark.asyncio
async def test_start_danmaku_clients_retries_failed_room_on_subsequent_call(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])

    failed_client = AsyncMock()
    failed_client.start = AsyncMock(side_effect=ConnectionError("start failed"))
    success_client = AsyncMock()

    with (
        patch(
            "plugins.live_monitor.live_monitor.DanmakuClient",
            side_effect=[failed_client, success_client],
        ),
        patch(
            "plugins.live_monitor.live_monitor.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await monitor._start_danmaku_clients()
        assert "111" not in monitor._danmaku_clients

        await monitor._start_danmaku_clients()

    assert monitor._danmaku_clients["111"] is success_client
    success_client.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_reload_config_starts_websocket_for_rooms_without_active_client(
    live_monitor_modules: tuple[Any, Any, Any],
) -> None:
    Config, LiveMonitor, LiveRoomState = live_monitor_modules
    monitor = _make_monitor(Config, LiveMonitor, LiveRoomState, ["111"])
    monitor.config.bilibili_cookie = None
    assert "111" not in monitor._danmaku_clients

    updated_config = Config(
        live_monitor_mapping={"111": ["group1"]},
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
            "_restart_single_danmaku_client",
            new_callable=AsyncMock,
        ) as restart_client,
    ):
        await monitor.reload_config()

    restart_client.assert_awaited_once_with("111")


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
