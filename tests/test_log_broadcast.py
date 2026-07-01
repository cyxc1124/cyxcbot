"""Tests for Web Admin log broadcast setup."""

from __future__ import annotations

import logging

from nonebot.log import LoguruHandler
from uvicorn.config import LOGGING_CONFIG

from shared.logging.broadcast import (
    LogBroadcastHub,
    LogEntry,
    bridge_uvicorn_loggers,
    entry_fingerprint,
    install_log_broadcast,
)


def _entry(message: str, *, level: str = "INFO") -> LogEntry:
    return LogEntry(
        ts="2026-01-01 00:00:00.000", level=level, logger="test", message=message
    )


def test_replay_window_entries_caught_up_without_subscriber() -> None:
    hub = LogBroadcastHub(max_history=10)
    hub.publish(_entry("initial"))
    history = hub.recent(limit=10, min_level="DEBUG")
    sent = {entry_fingerprint(entry) for entry in history}

    hub.publish(_entry("during-replay"))

    catch_up = [
        entry
        for entry in hub.recent(limit=10, min_level="DEBUG")
        if entry_fingerprint(entry) not in sent
    ]
    assert [entry.message for entry in catch_up] == ["during-replay"]

    queue = hub.subscribe()
    try:
        assert queue.qsize() == 0
        hub.publish(_entry("live"))
        assert queue.qsize() == 1
        assert queue.get_nowait().message == "live"
    finally:
        hub.unsubscribe(queue)


def test_buffer_catch_up_loops_until_ring_buffer_is_stable() -> None:
    hub = LogBroadcastHub(max_history=10)
    first = _entry("first")
    hub.publish(first)
    sent = {entry_fingerprint(first)}

    hub.publish(_entry("second"))
    batch = [
        entry
        for entry in hub.recent(limit=10, min_level="DEBUG")
        if entry_fingerprint(entry) not in sent
    ]
    assert [entry.message for entry in batch] == ["second"]
    for entry in batch:
        sent.add(entry_fingerprint(entry))

    hub.publish(_entry("third"))
    tail = [
        entry
        for entry in hub.recent(limit=10, min_level="DEBUG")
        if entry_fingerprint(entry) not in sent
    ]
    assert [entry.message for entry in tail] == ["third"]
    queue = hub.subscribe()
    try:
        assert queue.qsize() == 0
    finally:
        hub.unsubscribe(queue)


def test_burst_during_replay_does_not_register_subscriber() -> None:
    hub = LogBroadcastHub(max_history=300)
    history = hub.recent(limit=300, min_level="DEBUG")
    assert history == []

    for index in range(300):
        hub.publish(_entry(f"log-{index}"))

    queue = hub.subscribe()
    try:
        assert queue.qsize() == 0
    finally:
        hub.unsubscribe(queue)


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
