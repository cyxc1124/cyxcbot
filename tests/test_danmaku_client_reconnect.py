"""Tests for DanmakuClient device identity and reconnects."""

from __future__ import annotations

import asyncio
import importlib.util
import json
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
@pytest.mark.parametrize("cookie", [None, "DedeUserID=123; buvid3=existing"])
async def test_ensure_buvid_preserves_existing_or_anonymous_cookie(
    danmaku_client_module: Any, cookie: str | None
) -> None:
    session = MagicMock()
    client = danmaku_client_module.DanmakuClient(session, 123, cookie=cookie)

    await client._ensure_buvid()

    session.get.assert_not_called()
    assert client.cookie == cookie


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "; buvid3="])
async def test_missing_buvid_is_reused_in_cookie_token_request_and_auth(
    danmaku_client_module: Any, suffix: str
) -> None:
    module = danmaku_client_module
    session = MagicMock()
    spi_response = MagicMock()
    spi_response.json = AsyncMock(
        return_value={"code": 0, "data": {"b_3": "device-id"}}
    )
    info_response = MagicMock(status=200)
    info_response.json = AsyncMock(
        return_value={"code": 0, "data": {"token": "fresh", "host_list": []}}
    )
    session.get.return_value.__aenter__.side_effect = [
        spi_response,
        info_response,
        info_response,
    ]
    client = module.DanmakuClient(
        session, 123, cookie=f"DedeUserID=123; SESSDATA=session{suffix}"
    )
    client._ws = AsyncMock()

    with patch.object(module.wbi, "sign_params", new_callable=AsyncMock) as sign:
        sign.return_value = "id=123&signed=1"
        await client._update_danmu_info()
        await client._update_danmu_info()

    assert client.cookie == "DedeUserID=123; SESSDATA=session; buvid3=device-id"
    assert session.get.call_count == 3
    spi_response.raise_for_status.assert_called_once()
    for call in session.get.call_args_list[1:]:
        assert call.kwargs["headers"]["Cookie"] == "SESSDATA=session; buvid3=device-id"
    assert all(call.args[2] == client.cookie for call in sign.await_args_list)
    await client._send_auth()
    frame = client._ws.send_bytes.call_args.args[0]
    auth = json.loads(frame[module.WS.PACKAGE_HEADER_TOTAL_LENGTH :])
    assert (auth["uid"], auth["buvid"], auth["key"]) == (123, "device-id", "fresh")
    assert client._get_headers()["Cookie"] == client.cookie


@pytest.mark.asyncio
@pytest.mark.parametrize("signed_query", [None, "id=123&signed=1"])
async def test_token_request_omits_only_uid_cookie_and_keeps_login_session(
    danmaku_client_module: Any, signed_query: str | None
) -> None:
    module = danmaku_client_module
    session = MagicMock()
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={"code": 0, "data": {"token": "fresh", "host_list": []}}
    )
    session.get.return_value.__aenter__.return_value = response
    cookie = (
        "DedeUserID=123; SESSDATA=session; bili_jct=csrf; "
        "DedeUserID__ckMd5=checksum; sid=legacy; buvid3=device-id"
    )
    client = module.DanmakuClient(session, 123, cookie=cookie)

    with patch.object(module.wbi, "sign_params", new_callable=AsyncMock) as sign:
        sign.return_value = signed_query
        await client._update_danmu_info()

    assert session.get.call_count == 1
    assert session.get.call_args.kwargs["headers"]["Cookie"] == (
        "SESSDATA=session; bili_jct=csrf; DedeUserID__ckMd5=checksum; "
        "sid=legacy; buvid3=device-id"
    )
    assert client.cookie == cookie
    assert client._uid == 123
    assert client._get_headers()["Cookie"] == cookie


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"code": -352},
        {"code": 0, "data": {}},
        {"code": 0, "data": {"b_3": ""}},
        {"code": 0, "data": {"b_3": 123}},
        {"code": 0, "data": {"b_3": "bad; injected=cookie"}},
        {"code": 0, "data": {"b_3": "bad\r\nheader"}},
    ],
)
async def test_buvid_failure_stops_before_token_request_or_connection(
    danmaku_client_module: Any, payload: dict
) -> None:
    session = MagicMock()
    response = session.get.return_value.__aenter__.return_value
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=payload)
    client = danmaku_client_module.DanmakuClient(session, 123, cookie="DedeUserID=123")

    with patch.object(client, "_connect", new_callable=AsyncMock) as connect:
        with pytest.raises(ConnectionError, match="获取弹幕 buvid 失败"):
            await client.start()

    connect.assert_not_called()
    assert session.get.call_count == 1
    assert client.cookie == "DedeUserID=123"
    assert not client._buvid
    assert not client._running


@pytest.mark.asyncio
async def test_buvid_request_can_retry_after_network_failure(
    danmaku_client_module: Any,
) -> None:
    session = MagicMock()
    response = MagicMock()
    response.json = AsyncMock(return_value={"code": 0, "data": {"b_3": "device-id"}})
    session.get.return_value.__aenter__.side_effect = [TimeoutError(), response]
    client = danmaku_client_module.DanmakuClient(session, 123, cookie="DedeUserID=123")

    with pytest.raises(TimeoutError):
        await client._ensure_buvid()
    assert client.cookie == "DedeUserID=123"
    assert not client._buvid

    await client._ensure_buvid()
    assert client._buvid == "device-id"
    assert client.cookie == "DedeUserID=123; buvid3=device-id"


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
async def test_reconnect_refreshes_danmu_info_and_backs_off(
    danmaku_client_module: Any,
) -> None:
    client = _make_client(danmaku_client_module)
    order: list[str] = []
    attempts = 0

    async def refresh() -> None:
        order.append("refresh")

    async def flaky_connect() -> None:
        nonlocal attempts
        attempts += 1
        order.append("connect")
        if attempts < 6:
            raise ConnectionError("down")

    sleep = AsyncMock()
    with (
        patch.object(client, "_update_danmu_info", side_effect=refresh),
        patch.object(client, "_connect", side_effect=flaky_connect),
        patch("asyncio.sleep", sleep),
    ):
        client.schedule_reconnect()
        await client._reconnect_task

    assert order == ["refresh", "connect"] * 6
    assert [call.args[0] for call in sleep.await_args_list] == [3, 10, 20, 40, 60, 60]


@pytest.mark.asyncio
async def test_reconnect_connects_with_refreshed_token(
    danmaku_client_module: Any,
) -> None:
    client = _make_client(danmaku_client_module)
    client._danmu_info = {"token": "stale", "host_list": []}
    tokens_seen: list[str] = []

    async def refresh() -> None:
        client._danmu_info = {"token": "fresh", "host_list": []}

    async def connect() -> None:
        tokens_seen.append(client._danmu_info["token"])

    with (
        patch.object(client, "_update_danmu_info", side_effect=refresh),
        patch.object(client, "_connect", side_effect=connect),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        client.schedule_reconnect()
        await client._reconnect_task

    assert tokens_seen == ["fresh"]


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
