"""Tests for live monitor config hot reload."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "live_monitor"


def _ensure_package(name: str, path: Path | None = None) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    if path is not None:
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
    if "plugins.live_monitor.live_monitor" in sys.modules:
        return (
            sys.modules["plugins.live_monitor.config"].Config,
            sys.modules["plugins.live_monitor.live_monitor"].LiveMonitor,
            sys.modules["plugins.live_monitor.models"].LiveRoomState,
        )

    _ensure_package("plugins")
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


Config, LiveMonitor, LiveRoomState = _import_live_monitor_modules()


def _make_monitor(room_ids: list[str]) -> LiveMonitor:
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
async def test_reload_config_removes_deleted_room_state_and_websocket() -> None:
    monitor = _make_monitor(["111", "222"])
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
async def test_check_all_rooms_only_polls_configured_targets() -> None:
    monitor = _make_monitor(["222"])
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
