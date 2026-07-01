"""Live runtime log streaming for Web Admin."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from admin.auth.jwt import decode_access_token
from admin.deps import AdminUser, RequireSetup
from admin.schemas.logs import LogEntryResponse, RecentLogsResponse
from shared.db.models import User
from shared.logging.broadcast import (
    LEVEL_RANK,
    MAX_HISTORY,
    LogBroadcastHub,
    LogEntry,
    entry_fingerprint,
    get_log_hub,
)

router = APIRouter(
    tags=["logs"],
    dependencies=[RequireSetup],
)

_WS_AUTH_PROTOCOL = "access_token"


def _token_from_subprotocol(header: str | None) -> str | None:
    if not header:
        return None
    parts = [part.strip() for part in header.split(",")]
    for index, part in enumerate(parts):
        if part == _WS_AUTH_PROTOCOL and index + 1 < len(parts):
            return parts[index + 1]
    return None


async def _user_from_token(token: str) -> User | None:
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    username = str(payload["sub"])
    session = get_session()
    async with session.begin():
        user = await session.scalar(select(User).where(User.username == username))
        if user:
            await session.refresh(user)
            session.expunge(user)
        return user


def _serialize(entries: list[LogEntry]) -> list[LogEntryResponse]:
    return [LogEntryResponse.model_validate(entry.to_dict()) for entry in entries]


def _catch_up_entries(
    hub: LogBroadcastHub,
    *,
    sent: set[tuple[str, str, str, str]],
    limit: int,
    min_level: str,
) -> list[LogEntry]:
    return [
        entry
        for entry in hub.recent(limit=limit, min_level=min_level)
        if entry_fingerprint(entry) not in sent
    ]


async def _send_buffer_catch_up(
    websocket: WebSocket,
    hub: LogBroadcastHub,
    *,
    sent: set[tuple[str, str, str, str]],
    limit: int,
    min_level: str,
) -> None:
    """Replay ring-buffer deltas before subscribing so the live queue stays empty."""
    while True:
        catch_up = _catch_up_entries(hub, sent=sent, limit=limit, min_level=min_level)
        if not catch_up:
            return
        for entry in catch_up:
            await websocket.send_json(entry.to_dict())
            sent.add(entry_fingerprint(entry))


async def _drain_subscriber_backlog(
    websocket: WebSocket,
    queue: asyncio.Queue[LogEntry | None],
    *,
    sent: set[tuple[str, str, str, str]],
    threshold: str,
) -> bool:
    delivered = False
    while True:
        try:
            entry = queue.get_nowait()
        except asyncio.QueueEmpty:
            return delivered
        if entry is None:
            continue
        if not _level_gte(entry.level, threshold):
            continue
        fp = entry_fingerprint(entry)
        if fp in sent:
            continue
        await websocket.send_json(entry.to_dict())
        sent.add(fp)
        delivered = True


async def _handoff_to_live(
    websocket: WebSocket,
    hub: LogBroadcastHub,
    queue: asyncio.Queue[LogEntry | None],
    *,
    sent: set[tuple[str, str, str, str]],
    limit: int,
    min_level: str,
    threshold: str,
) -> None:
    """Subscribe handoff: merge ring-buffer delta and queued backlog before live loop."""
    while True:
        catch_up = _catch_up_entries(hub, sent=sent, limit=limit, min_level=min_level)
        progressed = False

        for entry in catch_up:
            fp = entry_fingerprint(entry)
            if fp in sent:
                continue
            await websocket.send_json(entry.to_dict())
            sent.add(fp)
            progressed = True

        if await _drain_subscriber_backlog(
            websocket, queue, sent=sent, threshold=threshold
        ):
            progressed = True

        if not progressed:
            return


@router.get("/logs/recent", response_model=RecentLogsResponse)
async def recent_logs(
    _: AdminUser,
    limit: int = Query(500, ge=1, le=2000),
    min_level: str = Query("DEBUG"),
):
    hub = get_log_hub()
    items = _serialize(hub.recent(limit=limit, min_level=min_level))
    return RecentLogsResponse(items=items, total_buffered=hub.history_size)


@router.websocket("/ws/logs")
async def stream_logs(
    websocket: WebSocket,
    min_level: str = Query(default="DEBUG"),
):
    token = _token_from_subprotocol(websocket.headers.get("sec-websocket-protocol"))
    user = await _user_from_token(token) if token else None
    if not user or not user.is_admin:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized"
        )
        return

    await websocket.accept(subprotocol=_WS_AUTH_PROTOCOL)
    hub = get_log_hub()

    try:
        threshold = min_level.upper()
        history = hub.recent(limit=MAX_HISTORY, min_level=min_level)
        sent = {entry_fingerprint(entry) for entry in history}

        for entry in history:
            await websocket.send_json(entry.to_dict())

        await _send_buffer_catch_up(
            websocket,
            hub,
            sent=sent,
            limit=MAX_HISTORY,
            min_level=min_level,
        )

        queue = hub.subscribe()
        try:
            await _handoff_to_live(
                websocket,
                hub,
                queue,
                sent=sent,
                limit=MAX_HISTORY,
                min_level=min_level,
                threshold=threshold,
            )

            # Live queue delivers each entry once; dedupe set only bridges replay/catch-up.
            sent.clear()

            while True:
                entry = await queue.get()
                if entry is None:
                    continue
                if not _level_gte(entry.level, threshold):
                    continue
                await websocket.send_json(entry.to_dict())
        finally:
            hub.unsubscribe(queue)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception:
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass


def _level_gte(level: str, minimum: str) -> bool:
    return LEVEL_RANK.get(level.upper(), 20) >= LEVEL_RANK.get(minimum.upper(), 20)
