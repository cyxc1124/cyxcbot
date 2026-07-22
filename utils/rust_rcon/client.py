"""Async WebRCON (WebSocket) client for Rust game servers.

Protocol reference: https://github.com/Facepunch/webrcon
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Final
from urllib.parse import quote

import aiohttp

# Facepunch webrcon uses identifiers > 1000 for request/response pairing.
REQUEST_IDENTIFIER: Final = 1001
WEBRCON_NAME: Final = "WebRcon"

DEFAULT_TIMEOUT_SECONDS: Final = 10.0
MAX_RESPONSE_CHARS: Final = 4000
RCON_CONNECTION_FAILED: Final = "RCON 连接失败，请检查服务器地址与端口配置"
RCON_TIMEOUT: Final = "RCON 连接或响应超时"
RCON_CLOSED: Final = "RCON 连接意外关闭"
RCON_WEBSOCKET_ERROR: Final = "RCON WebSocket 错误"


class RconError(Exception):
    """RCON connection or protocol error."""


class RconAuthError(RconError):
    """RCON password rejected."""


def _build_websocket_url(host: str, port: int, password: str) -> str:
    host = host.strip().strip("/")
    return f"ws://{host}:{port}/{quote(password, safe='')}"


def _truncate_response(text: str) -> str:
    if len(text) <= MAX_RESPONSE_CHARS:
        return text
    return text[: MAX_RESPONSE_CHARS - 20] + "\n…(输出已截断)"


def _build_command_packet(command: str, identifier: int) -> str:
    return json.dumps(
        {
            "Identifier": identifier,
            "Message": command,
            "Name": WEBRCON_NAME,
        },
        ensure_ascii=False,
    )


def _parse_response_message(data: dict[str, Any]) -> str:
    message = data.get("Message", "")
    if not isinstance(message, str):
        message = str(message)
    message = message.strip()
    return _truncate_response(message if message else "(无输出)")


def summarize_rcon_command_for_log(command: str) -> str:
    """Audit-safe command summary; never log argument values."""
    stripped = command.strip()
    if not stripped:
        return "(empty)"
    name, _, rest = stripped.partition(" ")
    if not rest:
        return name
    return f"{name} <{len(rest)} chars>"


async def execute_rcon_command(
    host: str,
    port: int,
    password: str,
    command: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Send *command* via Rust WebRCON and return the server response text."""
    url = _build_websocket_url(host, port, password)
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.ws_connect(url) as ws:
                await ws.send_str(_build_command_packet(command, REQUEST_IDENTIFIER))
                while True:
                    msg = await asyncio.wait_for(ws.receive(), timeout=timeout)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("Identifier") == REQUEST_IDENTIFIER:
                            return _parse_response_message(data)
                        continue
                    if msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                    ):
                        raise RconError(RCON_CLOSED)
                    if msg.type == aiohttp.WSMsgType.ERROR:
                        raise RconError(RCON_WEBSOCKET_ERROR)
    except aiohttp.WSServerHandshakeError as exc:
        raise RconAuthError("RCON 认证失败") from exc
    except asyncio.TimeoutError as exc:
        raise RconError(RCON_TIMEOUT) from exc
    except aiohttp.ClientError as exc:
        raise RconError(RCON_CONNECTION_FAILED) from exc
