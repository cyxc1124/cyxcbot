"""Log SSE authentication, replay, backpressure and disconnect regressions."""

import asyncio
import json
import sys
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from anyio import BrokenResourceError
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient
from starlette.requests import ClientDisconnect

from shared.logging.broadcast import (
    MAX_BUFFER_CATCH_UP_PASSES,
    MAX_HANDOFF_PASSES,
    SUBSCRIBER_QUEUE_SIZE,
    LogBroadcastHub,
    LogEntry,
)


def entry(message: str, level: str = "INFO") -> LogEntry:
    return LogEntry("", 0, "2026-01-01 00:00:00.000", level, "test", message)


@pytest.fixture
def api(monkeypatch):
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(sqlalchemy_database_url="sqlite+aiosqlite:///:memory:")
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    from admin.api.v1 import logs

    hub = LogBroadcastHub()
    monkeypatch.setattr(logs, "get_log_hub", lambda: hub)
    return logs, hub


@pytest.fixture
def app(api, monkeypatch):
    from admin import deps
    from admin.auth.jwt import create_access_token

    session = MagicMock()
    session.__aenter__.return_value = session
    session.scalar = AsyncMock(
        return_value=SimpleNamespace(username="admin", is_admin=True)
    )
    session.refresh = AsyncMock()
    monkeypatch.setattr(deps, "get_session", lambda: session)
    # Exercise FastAPI's native keep-alive path without waiting 15 seconds.
    monkeypatch.setattr("fastapi.routing._PING_INTERVAL", 0.02)
    application = FastAPI()
    application.include_router(api[0].router, prefix="/api/v1")
    application.dependency_overrides[deps.require_setup_complete] = lambda: None
    return application, session, create_access_token("admin")


@asynccontextmanager
async def connection(app, token, *, spec_version="2.3", send_hook=None):
    messages = asyncio.Queue()
    disconnected = asyncio.Event()

    async def receive():
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if disconnected.is_set():
            raise OSError("client disconnected")
        await messages.put(message)
        if send_hook:
            await send_hook(message)

    task = asyncio.create_task(
        app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": spec_version},
                "http_version": "1.1",
                "scheme": "http",
                "method": "GET",
                "path": "/api/v1/logs/stream",
                "query_string": b"min_level=INFO",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "client": ("127.0.0.1", 12345),
                "server": ("test", 80),
            },
            receive,
            send,
        )
    )
    try:
        yield messages, disconnected, task
    finally:
        disconnected.set()
        try:
            await asyncio.wait_for(task, timeout=1)
        except* ClientDisconnect, OSError:
            pass


async def next_body(messages):
    while True:
        message = await asyncio.wait_for(messages.get(), timeout=1)
        if message["type"] == "http.response.body":
            return message["body"]


@pytest.mark.parametrize("credential", ["missing", "invalid", "expired", "query"])
async def test_stream_requires_bearer_auth(app, credential):
    from admin.auth.jwt import create_access_token

    application, session, token = app
    headers = {}
    params = {}
    if credential == "invalid":
        headers["Authorization"] = "Bearer invalid"
    elif credential == "expired":
        headers["Authorization"] = f"Bearer {create_access_token('admin', {'exp': 0})}"
    elif credential == "query":
        params["token"] = token
    async with AsyncClient(
        transport=ASGITransport(application), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/logs/stream", headers=headers, params=params
        )
    assert response.status_code == 401
    session.scalar.assert_not_awaited()


async def test_stream_requires_admin_and_setup(app):
    from admin.deps import require_setup_complete

    application, session, token = app
    session.scalar.return_value.is_admin = False
    async with AsyncClient(
        transport=ASGITransport(application), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/logs/stream", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

        def not_initialized():
            raise HTTPException(403, "Setup required")

        application.dependency_overrides[require_setup_complete] = not_initialized
        session.scalar.return_value.is_admin = True
        response = await client.get(
            "/api/v1/logs/stream", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Setup required"


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
async def test_http_stream_replays_filters_pings_and_releases_subscription(
    api, app, spec_version
):
    _, hub = api
    application, _, token = app
    hub.publish(entry("历史\n中文"))
    hub.publish(entry("hidden", "DEBUG"))
    async with connection(application, token, spec_version=spec_version) as (
        messages,
        disconnected,
        task,
    ):
        start = await asyncio.wait_for(messages.get(), timeout=1)
        assert start["status"] == 200
        headers = dict(start["headers"])
        assert headers[b"content-type"] == b"text/event-stream; charset=utf-8"
        assert headers[b"cache-control"] == b"no-cache"
        assert headers[b"x-accel-buffering"] == b"no"
        history = json.loads(
            (await next_body(messages)).decode().removeprefix("data: ")
        )
        assert history["message"] == "历史\n中文"
        assert history["session_id"] == hub.session_id
        assert await next_body(messages) == b": ping\n\n"
        hub.publish(entry("live"))
        body = await next_body(messages)
        assert json.loads(body.decode().removeprefix("data: "))["message"] == "live"
        disconnected.set()
    assert task.done()
    assert not hub._subscribers


def test_catch_up_pass_limits_are_bounded():
    assert 1 <= MAX_BUFFER_CATCH_UP_PASSES <= 10
    assert 1 <= MAX_HANDOFF_PASSES <= 10


async def test_handoff_dedupes_delayed_worker_entry_in_live_queue(api, monkeypatch):
    logs, hub = api
    subscribe = hub.subscribe

    def subscribe_and_publish(**kwargs):
        queue = subscribe(**kwargs)
        worker = threading.Thread(target=hub.publish, args=(entry("handoff"),))
        worker.start()
        worker.join(timeout=1)
        assert not worker.is_alive()
        return queue

    monkeypatch.setattr(hub, "subscribe", subscribe_and_publish)
    stream = logs._stream_logs("INFO")
    try:
        assert (await anext(stream))["message"] == "handoff"
        asyncio.get_running_loop().call_soon(hub.publish, entry("fresh"))
        assert (await asyncio.wait_for(anext(stream), 1))["message"] == "fresh"
    finally:
        await stream.aclose()
    assert not hub._subscribers


async def test_replay_is_bounded_before_subscribing(api):
    logs, hub = api
    hub.publish(entry("0"))
    stream = logs._stream_logs("INFO")
    try:
        for index in range(1 + MAX_BUFFER_CATCH_UP_PASSES):
            assert (await anext(stream))["message"] == str(index)
            assert not hub._subscribers
            hub.publish(entry(str(index + 1)))
        assert (await anext(stream))["message"] == str(1 + MAX_BUFFER_CATCH_UP_PASSES)
        assert len(hub._subscribers) == 1
    finally:
        await stream.aclose()


async def test_overflow_ends_stream_and_reconnect_replays_tail(api):
    logs, hub = api
    stream = logs._stream_logs("INFO")
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    hub.publish(entry("live"))
    assert (await asyncio.wait_for(pending, 1))["message"] == "live"
    for index in range(SUBSCRIBER_QUEUE_SIZE + 1):
        hub.publish(entry(f"burst-{index}"))
    await asyncio.sleep(0)
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert not hub._subscribers
    replay = logs._stream_logs("INFO")
    try:
        messages = [
            (await anext(replay))["message"] for _ in range(SUBSCRIBER_QUEUE_SIZE + 2)
        ]
        assert messages[-1] == f"burst-{SUBSCRIBER_QUEUE_SIZE}"
        assert len(messages) == len(set(messages))
    finally:
        await replay.aclose()


async def test_idle_stream_cancellation_unsubscribes(api):
    logs, hub = api
    stream = logs._stream_logs("INFO")
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    assert len(hub._subscribers) == 1
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert not hub._subscribers


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
async def test_disconnect_during_slow_send_releases_subscription(
    api, app, spec_version
):
    _, hub = api
    application, _, token = app
    blocked = asyncio.Event()

    async def slow_send(message):
        if b"data:" in message.get("body", b""):
            blocked.set()
            await disconnected.wait()
            raise OSError("client disconnected")

    async with connection(
        application, token, spec_version=spec_version, send_hook=slow_send
    ) as (
        messages,
        disconnected,
        _,
    ):
        assert await next_body(messages) == b": ping\n\n"
        for index in range(10):
            hub.publish(entry(str(index)))
        await asyncio.wait_for(blocked.wait(), 1)
        assert hub._subscribers
        disconnected.set()
    assert not hub._subscribers


async def test_stream_cleanup_preserves_errors_without_disconnect(api):
    logs, hub = api

    async def receive():
        await asyncio.Event().wait()

    request = Request({"type": "http"}, receive=receive)
    with pytest.raises(ExceptionGroup) as raised:
        async with asynccontextmanager(logs._managed_log_stream)(
            request, min_level="INFO"
        ) as stream:
            pending = asyncio.create_task(anext(stream))
            await asyncio.sleep(0)
            hub.publish(entry("live"))
            await pending
            assert hub._subscribers
            raise BrokenResourceError
    assert isinstance(raised.value.exceptions[0], BrokenResourceError)
    assert not hub._subscribers
