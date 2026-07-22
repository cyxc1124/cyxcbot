"""Tests for Rust WebRCON client."""

from __future__ import annotations

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
async def test_execute_rcon_command_auth_fail(webrcon_auth_fail_server) -> None:
    host, port = webrcon_auth_fail_server
    with pytest.raises(RconAuthError):
        await execute_rcon_command(host, port, "wrong", "status")
