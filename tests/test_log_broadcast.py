"""Tests for Web Admin log broadcast setup."""

from __future__ import annotations

import logging

from nonebot.log import LoguruHandler
from uvicorn.config import LOGGING_CONFIG

from shared.logging.broadcast import (
    LogBroadcastHub,
    LogEntry,
    bridge_uvicorn_loggers,
    install_log_broadcast,
)


def _entry(message: str, *, level: str = "INFO") -> LogEntry:
    return LogEntry(ts="2026-01-01 00:00:00.000", level=level, logger="test", message=message)


def test_subscribe_with_recent_snapshots_before_replay_gap() -> None:
    hub = LogBroadcastHub(max_history=10)
    before = _entry("before")
    hub.publish(before)

    queue, history = hub.subscribe_with_recent(limit=10, min_level="DEBUG")

    after = _entry("after")
    hub.publish(after)

    assert history == [before]
    assert queue.qsize() == 1
    assert queue.get_nowait() == after


def test_subscribe_with_recent_respects_min_level() -> None:
    hub = LogBroadcastHub(max_history=10)
    hub.publish(_entry("debug", level="DEBUG"))
    hub.publish(_entry("info", level="INFO"))

    _queue, history = hub.subscribe_with_recent(limit=10, min_level="INFO")

    assert [item.message for item in history] == ["info"]


def test_install_log_broadcast_does_not_attach_uvicorn_handlers() -> None:
    """Web /logs should not use dedicated uvicorn stdlib handlers."""
    install_log_broadcast()
    for name in ("uvicorn", "uvicorn.error"):
        assert not logging.getLogger(name).handlers


def test_bridge_uvicorn_loggers_after_default_config() -> None:
    """Uvicorn default config must be overridden so logs reach LoguruHandler."""
    root = logging.getLogger()
    root.handlers = [LoguruHandler()]
    root.setLevel(logging.DEBUG)

    logging.config.dictConfig(LOGGING_CONFIG)
    assert logging.getLogger("uvicorn").propagate is False

    bridge_uvicorn_loggers()

    for name in ("uvicorn", "uvicorn.error", "uvicorn.asgi"):
        std_logger = logging.getLogger(name)
        assert not std_logger.handlers
        assert std_logger.propagate is True

    access_logger = logging.getLogger("uvicorn.access")
    assert not access_logger.handlers
    assert access_logger.propagate is False

    assert isinstance(root.handlers[0], LoguruHandler)
