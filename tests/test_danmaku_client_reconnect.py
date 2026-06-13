"""Tests for DanmakuClient reconnect deduplication."""

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

_TOUCCHED_MODULE_KEYS = (
    "plugins",
    "plugins.live_monitor",
    "plugins.live_monitor.danmaku_client",
    "utils.bilibili_api",
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


def _import_danmaku_client_module():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", PLUGIN_ROOT)

    wbi_mock = MagicMock()
    wbi_mock.sign_params = AsyncMock(return_value=None)
    sys.modules.setdefault("utils.bilibili_api", MagicMock(wbi=wbi_mock))

    path = PLUGIN_ROOT / "danmaku_client.py"
    spec = importlib.util.spec_from_file_location(
        "plugins.live_monitor.danmaku_client",
        path,
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["plugins.live_monitor.danmaku_client"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def danmaku_client_module() -> Iterator[Any]:
    saved = {key: sys.modules.get(key) for key in _TOUCCHED_MODULE_KEYS}
    module = _import_danmaku_client_module()
    yield module
    for key, value in saved.items():
        if value is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = value


def _make_client(module: Any) -> Any:
    session = MagicMock()
    client = module.DanmakuClient(session, room_id=123)
    client._running = True
    return client


@pytest.mark.asyncio
async def test_schedule_reconnect_deduplicates_concurrent_requests(
    danmaku_client_module: Any,
) -> None:
    client = _make_client(danmaku_client_module)
    connect_count = 0

    async def mock_connect() -> None:
        nonlocal connect_count
        connect_count += 1

    with (
        patch.object(client, "_connect", side_effect=mock_connect),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        client.schedule_reconnect()
        first_task = client._reconnect_task
        client.schedule_reconnect()
        client.schedule_reconnect()

        assert first_task is client._reconnect_task
        await first_task

    assert connect_count == 1
    assert client._reconnect_task is None


@pytest.mark.asyncio
async def test_failure_paths_share_single_reconnect_task(
    danmaku_client_module: Any,
) -> None:
    client = _make_client(danmaku_client_module)
    connect_gate = asyncio.Event()

    async def mock_connect() -> None:
        connect_gate.set()

    with (
        patch.object(client, "_connect", side_effect=mock_connect),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        client.schedule_reconnect()
        first_task = client._reconnect_task
        client.schedule_reconnect()

        assert first_task is client._reconnect_task
        await first_task
        await connect_gate.wait()

    assert client._reconnect_task is None


@pytest.mark.asyncio
async def test_reconnect_retries_in_same_task_without_spawning_duplicates(
    danmaku_client_module: Any,
) -> None:
    client = _make_client(danmaku_client_module)
    connect_attempts = 0

    async def flaky_connect() -> None:
        nonlocal connect_attempts
        connect_attempts += 1
        if connect_attempts < 2:
            raise ConnectionError("temporary failure")

    with (
        patch.object(client, "_connect", side_effect=flaky_connect),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        client.schedule_reconnect()
        reconnect_task = client._reconnect_task
        await reconnect_task

    assert connect_attempts == 2
    assert client._reconnect_task is None


@pytest.mark.asyncio
async def test_stop_cancels_in_flight_reconnect_task(
    danmaku_client_module: Any,
) -> None:
    client = _make_client(danmaku_client_module)
    reconnect_sleep_started = asyncio.Event()

    async def blocking_sleep(_delay: float) -> None:
        reconnect_sleep_started.set()
        await asyncio.Event().wait()

    with patch("asyncio.sleep", side_effect=blocking_sleep):
        client.schedule_reconnect()
        await reconnect_sleep_started.wait()

        assert client._reconnect_task is not None
        assert not client._reconnect_task.done()

        await client.stop()

    assert client._reconnect_task is None
    assert not client._running


@pytest.mark.asyncio
async def test_reconnect_cancels_heartbeat_and_message_tasks(
    danmaku_client_module: Any,
) -> None:
    client = _make_client(danmaku_client_module)

    heartbeat_cancelled = asyncio.Event()
    message_cancelled = asyncio.Event()

    async def heartbeat_loop() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            heartbeat_cancelled.set()
            raise

    async def message_loop() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            message_cancelled.set()
            raise

    client._heartbeat_task = asyncio.create_task(heartbeat_loop())
    client._message_task = asyncio.create_task(message_loop())

    with (
        patch.object(client, "_connect", new_callable=AsyncMock),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        client.schedule_reconnect()
        await client._reconnect_task

    await heartbeat_cancelled.wait()
    await message_cancelled.wait()
    assert client._heartbeat_task is None
    assert client._message_task is None
