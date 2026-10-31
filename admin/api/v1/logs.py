"""Live runtime log streaming for Web Admin."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Annotated, Any

from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, Query, Request
from fastapi.sse import EventSourceResponse

from admin.deps import AdminUser, RequireSetup
from admin.schemas.logs import LogEntryResponse, RecentLogsResponse
from shared.logging.broadcast import (
    LEVEL_RANK,
    MAX_BUFFER_CATCH_UP_PASSES,
    MAX_HANDOFF_PASSES,
    MAX_HISTORY,
    LogBroadcastHub,
    LogEntry,
    get_log_hub,
)

router = APIRouter(
    tags=["logs"],
    dependencies=[RequireSetup],
)


def _serialize(entries: list[LogEntry]) -> list[LogEntryResponse]:
    return [LogEntryResponse.model_validate(entry.to_dict()) for entry in entries]


def _catch_up_entries(
    hub: LogBroadcastHub,
    *,
    sent: set[int],
    limit: int,
    min_level: str,
) -> list[LogEntry]:
    return [
        entry
        for entry in hub.recent(limit=limit, min_level=min_level)
        if entry.entry_id not in sent
    ]


@router.get("/logs/recent", response_model=RecentLogsResponse)
async def recent_logs(
    _: AdminUser,
    limit: int = Query(500, ge=1, le=2000),
    min_level: str = Query("DEBUG"),
):
    hub = get_log_hub()
    items = _serialize(hub.recent(limit=limit, min_level=min_level))
    return RecentLogsResponse(
        items=items,
        total_buffered=hub.history_size,
        log_session_id=hub.session_id,
    )


async def _stream_logs(min_level: str) -> AsyncGenerator[dict[str, Any]]:
    hub = get_log_hub()
    threshold = min_level.upper()
    sent: set[int] = set()

    # Replay before subscribing so a slow history download cannot fill the live queue.
    for _ in range(1 + MAX_BUFFER_CATCH_UP_PASSES):
        catch_up = _catch_up_entries(
            hub, sent=sent, limit=MAX_HISTORY, min_level=min_level
        )
        if not catch_up:
            break
        for entry in catch_up:
            sent.add(entry.entry_id)
            yield entry.to_dict()

    queue = hub.subscribe(min_level=min_level)
    try:
        for _ in range(MAX_HANDOFF_PASSES):
            catch_up = _catch_up_entries(
                hub, sent=sent, limit=MAX_HISTORY, min_level=min_level
            )
            progressed = False
            for entry in catch_up:
                if not hub.is_subscribed(queue):
                    return
                sent.add(entry.entry_id)
                yield entry.to_dict()
                progressed = True

            # Merge queued entries with the ring delta before entering the live loop.
            while True:
                try:
                    entry = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if entry is None:
                    return
                if not _level_gte(entry.level, threshold):
                    continue
                if entry.entry_id in sent:
                    continue
                sent.add(entry.entry_id)
                yield entry.to_dict()
                progressed = True
            if not progressed:
                break

        # Worker callbacks may enqueue replayed entries after handoff returns.
        replay_end = max(sent, default=0)
        while True:
            entry = await queue.get()
            if entry is None:
                return
            if not _level_gte(entry.level, threshold):
                continue
            if entry.entry_id in sent:
                sent.remove(entry.entry_id)
                continue
            if entry.entry_id > replay_end:
                sent.clear()
            yield entry.to_dict()
    finally:
        hub.unsubscribe(queue)


async def _managed_log_stream(
    request: Request, min_level: str = Query(default="DEBUG")
) -> AsyncIterator[AsyncIterator[dict[str, Any]]]:
    stream = _stream_logs(min_level)
    try:
        yield stream
    except* BrokenResourceError:
        # shortcut: native SSE teardown races on disconnect; remove after FastAPI #15725 is fixed.
        if not await request.is_disconnected():
            raise
    finally:
        await stream.aclose()


@router.get("/logs/stream", response_class=EventSourceResponse)
async def stream_logs(
    _: AdminUser,
    stream: Annotated[AsyncIterator[dict[str, Any]], Depends(_managed_log_stream)],
) -> AsyncIterator[dict[str, Any]]:
    async for entry in stream:
        yield entry


def _level_gte(level: str, minimum: str) -> bool:
    return LEVEL_RANK.get(level.upper(), 20) >= LEVEL_RANK.get(minimum.upper(), 20)
