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
    return LogEntry(
        session_id="",
        entry_id=0,
        ts="2026-01-01 00:00:00.000",
        level=level,
        logger="test",
        message=message,
    )


def test_hub_assigns_stable_session_id() -> None:
    hub = LogBroadcastHub(max_history=10)
    hub.publish(_entry("a"))
    recent = hub.recent(limit=10, min_level="DEBUG")
    assert recent[0].session_id == hub.session_id


def test_distinct_hub_instances_have_distinct_session_ids() -> None:
    assert LogBroadcastHub().session_id != LogBroadcastHub().session_id


def test_buffer_catch_up_loops_until_ring_buffer_is_stable() -> None:
    hub = LogBroadcastHub(max_history=10)
    hub.publish(_entry("first"))
    recent = hub.recent(limit=10, min_level="DEBUG")
    sent = {recent[0].entry_id}

    hub.publish(_entry("second"))
    batch = [
        entry
        for entry in hub.recent(limit=10, min_level="DEBUG")
        if entry.entry_id not in sent
    ]
    assert [entry.message for entry in batch] == ["second"]
    for entry in batch:
        sent.add(entry.entry_id)

    hub.publish(_entry("third"))
    tail = [
        entry
        for entry in hub.recent(limit=10, min_level="DEBUG")
        if entry.entry_id not in sent
    ]
    assert [entry.message for entry in tail] == ["third"]
    queue = hub.subscribe()
    try:
        assert queue.qsize() == 0
    finally:
        hub.unsubscribe(queue)


def test_handoff_gap_entry_is_in_ring_buffer_before_subscribe() -> None:
    hub = LogBroadcastHub(max_history=10)
    hub.publish(_entry("initial"))
    sent = {entry.entry_id for entry in hub.recent(limit=10, min_level="DEBUG")}

    hub.publish(_entry("handoff-gap"))

    catch_up = [
        entry
        for entry in hub.recent(limit=10, min_level="DEBUG")
        if entry.entry_id not in sent
    ]
    assert [entry.message for entry in catch_up] == ["handoff-gap"]

    queue = hub.subscribe()
    try:
        assert queue.qsize() == 0
        hub.publish(_entry("live"))
        assert queue.qsize() == 1
    finally:
        hub.unsubscribe(queue)


def test_duplicate_fields_get_unique_entry_ids_for_dedupe() -> None:
    hub = LogBroadcastHub(max_history=10)
    shared = dict(
        session_id="",
        ts="2026-01-01 00:00:00.000",
        level="DEBUG",
        logger="test",
        message="poll complete",
    )
    hub.publish(LogEntry(entry_id=0, **shared))
    hub.publish(LogEntry(entry_id=0, **shared))

    recent = hub.recent(limit=10, min_level="DEBUG")
    assert len(recent) == 2
    assert recent[0].entry_id != recent[1].entry_id

    sent = {recent[0].entry_id}
    catch_up = [entry for entry in recent if entry.entry_id not in sent]
    assert len(catch_up) == 1
    assert catch_up[0].entry_id == recent[1].entry_id


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


def test_subscribe_filters_by_min_level_before_enqueue() -> None:
    """DEBUG flood must not fill an INFO subscriber's bounded queue."""
    hub = LogBroadcastHub(max_history=10)
    queue = hub.subscribe(min_level="INFO")
    try:
        for index in range(300):
            hub.publish(_entry(f"debug-{index}", level="DEBUG"))
        hub.publish(_entry("keep-me", level="INFO"))

        assert queue.qsize() == 1
        assert queue.get_nowait().message == "keep-me"
        assert queue in hub._subscribers
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
