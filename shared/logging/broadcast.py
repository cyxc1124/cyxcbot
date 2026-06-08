"""Capture loguru/stdlib logs into a ring buffer and fan-out to WebSocket subscribers."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

from nonebot.log import logger as nb_logger

# Ring buffer capacity for recent history (≈ last ~30–60 min at typical volume)
MAX_HISTORY = 2000

# Per-subscriber queue size; slow clients drop instead of blocking producers
SUBSCRIBER_QUEUE_SIZE = 256

LEVEL_RANK = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "SUCCESS": 25,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


@dataclass(frozen=True)
class LogEntry:
    ts: str
    level: str
    logger: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_loguru_record(cls, record: dict[str, Any]) -> LogEntry:
        time_value = record["time"]
        if isinstance(time_value, datetime):
            ts = time_value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        else:
            ts = str(time_value)
        return cls(
            ts=ts,
            level=str(record["level"].name),
            logger=str(record["name"]),
            message=str(record["message"]),
        )

    @classmethod
    def from_logging_record(cls, record: logging.LogRecord) -> LogEntry:
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return cls(
            ts=ts,
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
        )


def _level_rank(level: str) -> int:
    return LEVEL_RANK.get(level.upper(), 20)


class LogBroadcastHub:
    """Thread-safe hub storing recent logs and broadcasting to asyncio subscribers."""

    def __init__(self, max_history: int = MAX_HISTORY) -> None:
        self._max_history = max_history
        self._history: deque[LogEntry] = deque(maxlen=max_history)
        self._subscribers: set[asyncio.Queue[LogEntry | None]] = set()
        self._lock = threading.Lock()

    def publish(self, entry: LogEntry) -> None:
        with self._lock:
            self._history.append(entry)
            dead: list[asyncio.Queue[LogEntry | None]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(entry)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._subscribers.discard(queue)

    def recent(self, *, limit: int = 500, min_level: str = "DEBUG") -> list[LogEntry]:
        threshold = _level_rank(min_level)
        with self._lock:
            items = list(self._history)
        filtered = [item for item in items if _level_rank(item.level) >= threshold]
        if limit <= 0:
            return filtered
        return filtered[-limit:]

    def subscribe(self) -> asyncio.Queue[LogEntry | None]:
        queue: asyncio.Queue[LogEntry | None] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[LogEntry | None]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    @property
    def history_size(self) -> int:
        with self._lock:
            return len(self._history)


_hub: LogBroadcastHub | None = None
_installed = False


def get_log_hub() -> LogBroadcastHub:
    global _hub
    if _hub is None:
        _hub = LogBroadcastHub()
    return _hub


def _loguru_sink(message: Any) -> None:
    entry = LogEntry.from_loguru_record(message.record)
    get_log_hub().publish(entry)


class _BroadcastLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry.from_logging_record(record)
            get_log_hub().publish(entry)
        except Exception:
            self.handleError(record)


def install_log_broadcast() -> None:
    """Register loguru sink and stdlib handler (idempotent)."""
    global _installed
    if _installed:
        return
    _installed = True
    get_log_hub()

    nb_logger.add(
        _loguru_sink,
        format="{message}",
        level="DEBUG",
        enqueue=True,
        catch=True,
    )

    handler = _BroadcastLogHandler()
    handler.setLevel(logging.DEBUG)
    for name in ("uvicorn", "uvicorn.error"):
        std_logger = logging.getLogger(name)
        std_logger.addHandler(handler)
