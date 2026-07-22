"""Minimal async Source RCON (TCP) client — stdlib only."""

from __future__ import annotations

import asyncio
import struct
from typing import Final

SERVERDATA_RESPONSE_VALUE: Final = 0
SERVERDATA_AUTH_RESPONSE: Final = 2
SERVERDATA_EXECCOMMAND: Final = 2
SERVERDATA_AUTH: Final = 3

DEFAULT_TIMEOUT_SECONDS: Final = 10.0
MAX_RESPONSE_CHARS: Final = 4000


class RconError(Exception):
    """RCON connection or protocol error."""


class RconAuthError(RconError):
    """RCON password rejected."""


def _pack_packet(request_id: int, packet_type: int, body: str) -> bytes:
    payload = (
        struct.pack("<ii", request_id, packet_type) + body.encode("utf-8") + b"\x00\x00"
    )
    return struct.pack("<i", len(payload)) + payload


def _unpack_packet(data: bytes) -> tuple[int, int, str]:
    if len(data) < 8:
        raise RconError("RCON 响应包过短")
    request_id, packet_type = struct.unpack_from("<ii", data, 0)
    body_bytes = data[8:].rstrip(b"\x00")
    body = body_bytes.decode("utf-8", errors="replace")
    return request_id, packet_type, body


async def _read_packet(reader: asyncio.StreamReader) -> tuple[int, int, str]:
    size_bytes = await reader.readexactly(4)
    (size,) = struct.unpack("<i", size_bytes)
    if size < 8:
        raise RconError("RCON 响应长度无效")
    payload = await reader.readexactly(size)
    return _unpack_packet(payload)


def _truncate_response(text: str) -> str:
    if len(text) <= MAX_RESPONSE_CHARS:
        return text
    return text[: MAX_RESPONSE_CHARS - 20] + "\n…(输出已截断)"


async def execute_rcon_command(
    host: str,
    port: int,
    password: str,
    command: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Send *command* via Source RCON and return the server response text."""
    connect_coro = asyncio.open_connection(host, port)
    reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
    try:
        writer.write(_pack_packet(1, SERVERDATA_AUTH, password))
        await writer.drain()

        while True:
            request_id, packet_type, _ = await asyncio.wait_for(
                _read_packet(reader), timeout
            )
            if packet_type == SERVERDATA_AUTH_RESPONSE:
                if request_id == -1:
                    raise RconAuthError("RCON 认证失败")
                break

        writer.write(_pack_packet(2, SERVERDATA_EXECCOMMAND, command))
        await writer.drain()

        parts: list[str] = []
        while True:
            request_id, packet_type, body = await asyncio.wait_for(
                _read_packet(reader), timeout
            )
            if packet_type != SERVERDATA_RESPONSE_VALUE or request_id != 2:
                continue
            if not body:
                break
            parts.append(body)

        combined = "\n".join(parts).strip()
        return _truncate_response(combined if combined else "(无输出)")
    except asyncio.TimeoutError as exc:
        raise RconError("RCON 连接或响应超时") from exc
    except asyncio.IncompleteReadError as exc:
        raise RconError("RCON 连接意外关闭") from exc
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
