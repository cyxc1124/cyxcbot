"""Tests for Rust WebRCON client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from aiohttp import web

from utils.rust_rcon.client import (
    REQUEST_IDENTIFIER,
    RconAuthError,
    execute_rcon_command,
)


async def _websocket_handler(request: web.Request) -> web.WebSocketResponse:
    password = request.match_info["password"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    if password != "pass":
        await ws.close()
        return ws

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            await ws.send_str(
                json.dumps(
                    {
                        "Identifier": data["Identifier"],
                        "Message": "ok",
                        "Type": "Generic",
                    }
                )
            )
    return ws


async def _websocket_auth_fail(_request: web.Request) -> web.Response:
    raise web.HTTPUnauthorized()


@pytest.fixture
async def webrcon_server() -> AsyncIterator[tuple[str, int]]:
    app = web.Application()
    app.router.add_get("/{password}", _websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sock = site._server.sockets[0].getsockname()
    try:
        yield sock[0], sock[1]
    finally:
        await runner.cleanup()


@pytest.fixture
async def webrcon_auth_fail_server() -> AsyncIterator[tuple[str, int]]:
    app = web.Application()
    app.router.add_get("/{password}", _websocket_auth_fail)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sock = site._server.sockets[0].getsockname()
    try:
        yield sock[0], sock[1]
    finally:
        await runner.cleanup()


@pytest.fixture
async def webrcon_spam_server() -> AsyncIterator[tuple[str, int]]:
    async def _handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        counter = 0
        while True:
            await ws.send_str(
                json.dumps(
                    {
                        "Identifier": 0,
                        "Message": f"log {counter}",
                        "Type": "Generic",
                    }
                )
            )
            counter += 1
            await asyncio.sleep(0.01)

    app = web.Application()
    app.router.add_get("/{password}", _handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sock = site._server.sockets[0].getsockname()
    try:
        yield sock[0], sock[1]
    finally:
        await runner.cleanup()


@pytest.fixture
async def webrcon_long_response_server() -> AsyncIterator[tuple[str, int]]:
    async def _handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                await ws.send_str(
                    json.dumps(
                        {
                            "Identifier": data["Identifier"],
                            "Message": "x" * 5000,
                            "Type": "Generic",
                        }
                    )
                )
        return ws

    app = web.Application()
    app.router.add_get("/{password}", _handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sock = site._server.sockets[0].getsockname()
    try:
        yield sock[0], sock[1]
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_execute_rcon_command_success(webrcon_server) -> None:
    host, port = webrcon_server
    result = await execute_rcon_command(host, port, "pass", "status")
    assert result == "ok"


@pytest.mark.asyncio
async def test_build_command_packet_matches_webrcon_format() -> None:
    from utils.rust_rcon.client import _build_command_packet

    payload = json.loads(_build_command_packet("status", REQUEST_IDENTIFIER))
    assert payload == {
        "Identifier": REQUEST_IDENTIFIER,
        "Message": "status",
        "Name": "WebRcon",
    }


@pytest.mark.asyncio
async def test_execute_rcon_command_truncates_by_default(
    webrcon_long_response_server,
) -> None:
    host, port = webrcon_long_response_server
    result = await execute_rcon_command(host, port, "pass", "status")
    assert len(result) < 5000
    assert "截断" in result


@pytest.mark.asyncio
async def test_execute_rcon_command_can_skip_truncation(
    webrcon_long_response_server,
) -> None:
    host, port = webrcon_long_response_server
    result = await execute_rcon_command(
        host, port, "pass", "status", truncate_response=False
    )
    assert len(result) == 5000


@pytest.mark.asyncio
async def test_execute_rcon_command_times_out_on_non_matching_spam(
    webrcon_spam_server,
) -> None:
    from utils.rust_rcon.client import RCON_TIMEOUT, RconError

    host, port = webrcon_spam_server
    with pytest.raises(RconError, match=RCON_TIMEOUT):
        await execute_rcon_command(host, port, "pass", "status", timeout=0.5)


@pytest.mark.asyncio
async def test_execute_rcon_command_auth_fail(webrcon_auth_fail_server) -> None:
    host, port = webrcon_auth_fail_server
    with pytest.raises(RconAuthError):
        await execute_rcon_command(host, port, "wrong", "status")


def test_summarize_rcon_command_for_log_redacts_arguments() -> None:
    from utils.rust_rcon.client import summarize_rcon_command_for_log

    assert summarize_rcon_command_for_log("status") == "status"
    assert (
        summarize_rcon_command_for_log("rcon.password s3cr3t")
        == "rcon.password <6 chars>"
    )
    assert summarize_rcon_command_for_log("  say hello  ") == "say <5 chars>"


@pytest.mark.asyncio
async def test_execute_rcon_command_connection_error_hides_password() -> None:
    from utils.rust_rcon.client import RCON_CONNECTION_FAILED, RconError

    with pytest.raises(RconError, match=RCON_CONNECTION_FAILED) as exc_info:
        await execute_rcon_command(
            "127.0.0.1",
            1,
            "s3cr3t-pass",
            "status",
            timeout=0.5,
        )
    assert "s3cr3t" not in str(exc_info.value)


def test_build_websocket_url_brackets_ipv6_literals() -> None:
    from utils.rust_rcon.client import _build_websocket_url

    assert _build_websocket_url("::1", 28016, "pass") == "ws://[::1]:28016/pass"
    assert (
        _build_websocket_url("2001:db8::1", 28016, "pass")
        == "ws://[2001:db8::1]:28016/pass"
    )
    assert _build_websocket_url("[::1]", 28016, "pass") == "ws://[::1]:28016/pass"
    assert (
        _build_websocket_url("example.com", 28016, "pass")
        == "ws://example.com:28016/pass"
    )
    assert (
        _build_websocket_url("192.168.1.1", 28016, "pass")
        == "ws://192.168.1.1:28016/pass"
    )
