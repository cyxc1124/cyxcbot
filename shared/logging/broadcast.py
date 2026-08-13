"""Capture loguru logs into a ring buffer and fan-out to WebSocket subscribers."""

from __future__ import annotations

import asyncio
import heapq
import logging
import re
import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any

from nonebot.log import logger as nb_logger

# Per-tier ring capacity. INFO+ and DEBUG are stored separately so monitor
# DEBUG floods cannot starve the default Web /logs INFO view.
MAX_HISTORY = 2000

# Per-subscriber queue size; slow clients drop instead of blocking producers
SUBSCRIBER_QUEUE_SIZE = 256

# Cap websocket replay loops so sustained DEBUG cannot spin forever pre-subscribe.
MAX_BUFFER_CATCH_UP_PASSES = 5
MAX_HANDOFF_PASSES = 5

LEVEL_RANK = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "SUCCESS": 25,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
_INFO_RANK = LEVEL_RANK["INFO"]

# nonebot.message.handle_event SUCCESS dump, with or without color tags:
# "<m>OneBot V11 123</m> | [message.group.normal]: Message ..."
_ADAPTER_EVENT_DUMP_RE = re.compile(r"^(?:<m>)?[^<\n]+(?:</m>)? \| \[[\w.]+\]: ")


@dataclass(frozen=True)
class LogEntry:
    session_id: str
    entry_id: int
    ts: str
    level: str
    logger: str
    message: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)

    @classmethod
    def from_loguru_record(cls, record: dict[str, Any]) -> LogEntry:
        time_value = record["time"]
        if isinstance(time_value, datetime):
            ts = time_value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        else:
            ts = str(time_value)
        return cls(
            session_id="",
            entry_id=0,
            ts=ts,
            level=str(record["level"].name),
            logger=str(record["name"]),
            message=str(record["message"]),
        )


def _level_rank(level: str) -> int:
    return LEVEL_RANK.get(level.upper(), 20)


class LogBroadcastHub:
    """Thread-safe hub storing recent logs and broadcasting to asyncio subscribers."""

    def __init__(self, max_history: int = MAX_HISTORY) -> None:
        self._max_history = max_history
        # Split tiers: default Web view is INFO; DEBUG must not evict it.
        self._info_history: deque[LogEntry] = deque(maxlen=max_history)
        self._debug_history: deque[LogEntry] = deque(maxlen=max_history)
        # queue -> min level rank; filter before enqueue so DEBUG flood cannot
        # fill INFO subscribers' 256-slot queues.
        self._subscribers: dict[asyncio.Queue[LogEntry | None], int] = {}
        self._lock = threading.Lock()
        self._seq = 0
        self._session_id = uuid.uuid4().hex

    @property
    def session_id(self) -> str:
        return self._session_id

    def publish(self, entry: LogEntry) -> None:
        with self._lock:
            self._seq += 1
            entry = replace(entry, session_id=self._session_id, entry_id=self._seq)
            entry_rank = _level_rank(entry.level)
            if entry_rank >= _INFO_RANK:
                self._info_history.append(entry)
            else:
                self._debug_history.append(entry)
            dead: list[asyncio.Queue[LogEntry | None]] = []
            for queue, threshold in self._subscribers.items():
                if entry_rank < threshold:
                    continue
                try:
                    queue.put_nowait(entry)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._subscribers.pop(queue, None)
                # Drop backlog so None is next; otherwise a slow send_json loop
                # may never reach the sentinel. Ring buffer still has history.
                while True:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

    def recent(self, *, limit: int = 500, min_level: str = "DEBUG") -> list[LogEntry]:
        threshold = _level_rank(min_level)
        with self._lock:
            if threshold >= _INFO_RANK:
                items = [
                    item
                    for item in self._info_history
                    if _level_rank(item.level) >= threshold
                ]
            else:
                # Both deques are append-ordered by monotonic entry_id.
                items = list(
                    heapq.merge(
                        self._debug_history,
                        self._info_history,
                        key=lambda item: item.entry_id,
                    )
                )
                items = [item for item in items if _level_rank(item.level) >= threshold]
        if limit <= 0:
            return items
        return items[-limit:]

    def subscribe(self, *, min_level: str = "DEBUG") -> asyncio.Queue[LogEntry | None]:
        queue: asyncio.Queue[LogEntry | None] = asyncio.Queue(
            maxsize=SUBSCRIBER_QUEUE_SIZE
        )
        with self._lock:
            self._subscribers[queue] = _level_rank(min_level)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[LogEntry | None]) -> None:
        with self._lock:
            self._subscribers.pop(queue, None)

    def is_subscribed(self, queue: asyncio.Queue[LogEntry | None]) -> bool:
        with self._lock:
            return queue in self._subscribers

    @property
    def history_size(self) -> int:
        with self._lock:
            return len(self._info_history) + len(self._debug_history)


_hub: LogBroadcastHub | None = None
_installed = False


def get_log_hub() -> LogBroadcastHub:
    global _hub
    if _hub is None:
        _hub = LogBroadcastHub()
    return _hub


def _level_name(record: dict[str, Any]) -> str:
    level = record["level"]
    return str(getattr(level, "name", level))


def _source_path(record: dict[str, Any]) -> str:
    file_info = record.get("file")
    path = getattr(file_info, "path", "") if file_info is not None else ""
    return str(path).replace("\\", "/")


def web_broadcast_filter(record: dict[str, Any]) -> bool:
    """Keep this record in Web /logs.

    NoneBot inbound event SUCCESS dumps and Matcher dispatch INFO stay on
    console and the file sink; a busy group otherwise floods /logs.
    """
    message = str(record["message"])
    if message.startswith("Event will be handled by Matcher("):
        return False
    if message.startswith("Matcher(") and message.endswith(" running complete"):
        return False
    if _level_name(record) == "SUCCESS" and (
        _source_path(record).endswith("/nonebot/message.py")
        or _ADAPTER_EVENT_DUMP_RE.match(message)
    ):
        return False
    return True


def _loguru_sink(message: Any) -> None:
    entry = LogEntry.from_loguru_record(message.record)
    get_log_hub().publish(entry)


UVICORN_SERVICE_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.asgi")
UVICORN_ACCESS_LOGGER_NAME = "uvicorn.access"


def bridge_uvicorn_loggers() -> None:
    """Route uvicorn service loggers through the root LoguruHandler.

    Uvicorn's default ``LOGGING_CONFIG`` installs StreamHandlers and sets
    ``propagate=False`` on its logger tree, so records never reach the bridge
    installed in ``bot.py``. Call after ``uvicorn.Config(..., log_config=None)``.

    ``uvicorn.access`` is silenced here; pair with ``access_log=False`` on
    ``uvicorn.Config`` so HTTP request lines do not flood Web /logs.
    """
    for name in UVICORN_SERVICE_LOGGER_NAMES:
        std_logger = logging.getLogger(name)
        std_logger.handlers.clear()
        std_logger.propagate = True

    access_logger = logging.getLogger(UVICORN_ACCESS_LOGGER_NAME)
    access_logger.handlers.clear()
    access_logger.propagate = False


def install_log_broadcast() -> None:
    """Register loguru sink for Web Admin /logs (idempotent).

    Stdlib logs (e.g. uvicorn) reach this sink via LoguruHandler in bot.py.
    Uvicorn must use ``log_config=None`` plus ``bridge_uvicorn_loggers()`` so its
    loggers propagate to root; do not attach separate stdlib handlers here.

    NoneBot inbound event dumps and Matcher dispatch lines are filtered out so
    they remain on stdout / file logs only.
    """
    global _installed
    if _installed:
        return
    _installed = True
    get_log_hub()

    nb_logger.add(
        _loguru_sink,
        format="{message}",
        level="DEBUG",
        filter=web_broadcast_filter,
        enqueue=True,
        catch=True,
    )
