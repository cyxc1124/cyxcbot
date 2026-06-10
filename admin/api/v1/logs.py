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
from shared.logging.broadcast import LEVEL_RANK, LogEntry, get_log_hub

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
        for entry in hub.recent(limit=500, min_level=min_level):
            await websocket.send_json(entry.to_dict())

        queue = hub.subscribe()
        threshold = min_level.upper()
        try:
            while True:
                entry = await queue.get()
                if entry is None:
                    continue
                if _level_gte(entry.level, threshold):
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
