"""Tests for Source RCON client."""

from __future__ import annotations

import asyncio
import struct

import pytest

from utils.rust_rcon.client import (
    SERVERDATA_AUTH,
    SERVERDATA_AUTH_RESPONSE,
    SERVERDATA_EXECCOMMAND,
    SERVERDATA_RESPONSE_VALUE,
    RconAuthError,
    _pack_packet,
    execute_rcon_command,
)


async def _read_request(reader: asyncio.StreamReader) -> tuple[int, int, str]:
    size_bytes = await reader.readexactly(4)
    (size,) = struct.unpack("<i", size_bytes)
    payload = await reader.readexactly(size)
    request_id, packet_type = struct.unpack_from("<ii", payload, 0)
    body_bytes = payload[8:].rstrip(b"\x00")
    body = body_bytes.decode("utf-8")
    return request_id, packet_type, body


async def _handle_rcon_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        _, packet_type, body = await _read_request(reader)
        assert packet_type == SERVERDATA_AUTH
        assert body == "pass"

        writer.write(_pack_packet(1, SERVERDATA_AUTH_RESPONSE, ""))
        await writer.drain()

        _, packet_type, body = await _read_request(reader)
        assert packet_type == SERVERDATA_EXECCOMMAND
        assert body == "status"

        writer.write(_pack_packet(2, SERVERDATA_RESPONSE_VALUE, "ok"))
        writer.write(_pack_packet(2, SERVERDATA_RESPONSE_VALUE, ""))
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def _handle_rcon_auth_fail(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    await _read_request(reader)
    writer.write(_pack_packet(-1, SERVERDATA_AUTH_RESPONSE, ""))
    await writer.drain()
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_execute_rcon_command_success() -> None:
    server = await asyncio.start_server(_handle_rcon_client, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    try:
        result = await execute_rcon_command(host, port, "pass", "status")
        assert result == "ok"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_execute_rcon_command_auth_fail() -> None:
    server = await asyncio.start_server(_handle_rcon_auth_fail, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    try:
        with pytest.raises(RconAuthError):
            await execute_rcon_command(host, port, "wrong", "status")
    finally:
        server.close()
        await server.wait_closed()
