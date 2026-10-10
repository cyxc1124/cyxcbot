"""Tests for Web Admin log websocket replay limits."""

import asyncio
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import nonebot
import pytest
from fastapi import WebSocketDisconnect

from shared.logging.broadcast import (
    MAX_BUFFER_CATCH_UP_PASSES,
    MAX_HANDOFF_PASSES,
    LogBroadcastHub,
    LogEntry,
)


def test_catch_up_pass_limits_are_bounded() -> None:
    assert 1 <= MAX_BUFFER_CATCH_UP_PASSES <= 10
    assert 1 <= MAX_HANDOFF_PASSES <= 10


async def test_handoff_dedupes_delayed_worker_entry_in_live_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(sqlalchemy_database_url="sqlite+aiosqlite:///:memory:")
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    from admin.api.v1 import logs as api

    hub = LogBroadcastHub()
    entry = LogEntry("", 0, "2026-01-01 00:00:00.000", "INFO", "test", "handoff")
    subscribe = hub.subscribe

    def subscribe_and_publish(**kwargs):
        queue = subscribe(**kwargs)
        worker = threading.Thread(target=hub.publish, args=(entry,))
        worker.start()
        worker.join(timeout=1)
        assert not worker.is_alive()
        return queue

    messages = []

    async def send_json(payload):
        messages.append(payload["message"])
        if len(messages) == 1:
            asyncio.get_running_loop().call_soon(
                hub.publish, LogEntry("", 0, entry.ts, "INFO", "test", "fresh")
            )
        if payload["message"] == "fresh":
            raise WebSocketDisconnect

    websocket = SimpleNamespace(
        headers={"sec-websocket-protocol": "access_token,test"},
        accept=AsyncMock(),
        send_json=send_json,
        close=AsyncMock(),
    )
    monkeypatch.setattr(hub, "subscribe", subscribe_and_publish)
    monkeypatch.setattr(api, "get_log_hub", lambda: hub)
    monkeypatch.setattr(
        api, "_user_from_token", AsyncMock(return_value=SimpleNamespace(is_admin=True))
    )
    await api.stream_logs(websocket, min_level="INFO")
    assert messages == ["handoff", "fresh"]
