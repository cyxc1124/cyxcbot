"""Async WebRCON (WebSocket) client for Rust game servers.

Protocol reference: https://github.com/Facepunch/webrcon
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
from typing import Any, Final
from urllib.parse import quote, urlunparse

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


def _format_host_for_netloc(host: str) -> str:
    host = host.strip().strip("/")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(ip, ipaddress.IPv6Address):
        return f"[{ip}]"
    return str(ip)


def _build_websocket_url(host: str, port: int, password: str) -> str:
    netloc = f"{_format_host_for_netloc(host)}:{port}"
    path = f"/{quote(password, safe='')}"
    return urlunparse(("ws", netloc, path, "", "", ""))


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


def _extract_response_message(data: dict[str, Any]) -> str:
    message = data.get("Message", "")
    if not isinstance(message, str):
        message = str(message)
    message = message.strip()
    return message if message else "(无输出)"


def _parse_response_message(data: dict[str, Any], *, truncate: bool) -> str:
    message = _extract_response_message(data)
    if truncate:
        return _truncate_response(message)
    return message


def summarize_rcon_command_for_log(command: str) -> str:
    """Audit-safe command summary; never log argument values."""
    stripped = command.strip()
    if not stripped:
        return "(empty)"
    name, _, rest = stripped.partition(" ")
    if not rest:
        return name
    return f"{name} <{len(rest)} chars>"


def _abort_websocket(ws: aiohttp.ClientWebSocketResponse) -> None:
    """Drop the WebSocket without waiting for Rust's slow close handshake."""
    if ws.closed:
        return
    writer = ws._writer
    if writer is not None:
        # ponytail: WebRCON servers often stall WS close for ~10s; abort avoids
        # blocking callers on ``async with ws_connect`` __aexit__.
        writer.transport.abort()


async def _exchange_rcon_command(
    url: str,
    command: str,
    *,
    timeout: float,
    truncate: bool,
) -> str:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    def _remaining() -> float:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise RconError(RCON_TIMEOUT)
        return remaining

    session = aiohttp.ClientSession()
    ws: aiohttp.ClientWebSocketResponse | None = None
    try:
        try:
            ws = await asyncio.wait_for(
                session.ws_connect(url),
                timeout=_remaining(),
            )
        except asyncio.TimeoutError as exc:
            raise RconError(RCON_TIMEOUT) from exc
        await ws.send_str(_build_command_packet(command, REQUEST_IDENTIFIER))
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive(), timeout=_remaining())
            except asyncio.TimeoutError as exc:
                raise RconError(RCON_TIMEOUT) from exc
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("Identifier") == REQUEST_IDENTIFIER:
                    return _parse_response_message(data, truncate=truncate)
                continue
            if msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
            ):
                raise RconError(RCON_CLOSED)
            if msg.type == aiohttp.WSMsgType.ERROR:
                raise RconError(RCON_WEBSOCKET_ERROR)
    finally:
        if ws is not None:
            _abort_websocket(ws)
        await session.close()


async def execute_rcon_command(
    host: str,
    port: int,
    password: str,
    command: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    truncate_response: bool = True,
) -> str:
    """Send *command* via Rust WebRCON and return the server response text."""
    url = _build_websocket_url(host, port, password)

    try:
        return await _exchange_rcon_command(
            url,
            command,
            timeout=timeout,
            truncate=truncate_response,
        )
    except aiohttp.WSServerHandshakeError as exc:
        raise RconAuthError("RCON 认证失败") from exc
    except aiohttp.ClientError as exc:
        raise RconError(RCON_CONNECTION_FAILED) from exc
