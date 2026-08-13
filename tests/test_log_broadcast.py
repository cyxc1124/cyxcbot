"""Tests for Web Admin log broadcast setup."""

from __future__ import annotations

import logging

from nonebot.log import LoguruHandler
from uvicorn.config import LOGGING_CONFIG

from shared.logging.broadcast import (
    SUBSCRIBER_QUEUE_SIZE,
    LogBroadcastHub,
    LogEntry,
    bridge_uvicorn_loggers,
    install_log_broadcast,
    web_broadcast_filter,
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
        assert hub.is_subscribed(queue)
    finally:
        hub.unsubscribe(queue)


def test_debug_flood_does_not_starve_info_history() -> None:
    """Default INFO view must keep its own ring after long DEBUG polling."""
    hub = LogBroadcastHub(max_history=10)
    for index in range(10):
        hub.publish(_entry(f"info-{index}", level="INFO"))
    for index in range(100):
        hub.publish(_entry(f"debug-{index}", level="DEBUG"))

    recent = hub.recent(limit=10, min_level="INFO")
    assert len(recent) == 10
    assert [entry.message for entry in recent] == [f"info-{i}" for i in range(10)]
    assert hub.history_size == 20


def test_debug_recent_merges_tiers_in_entry_id_order() -> None:
    hub = LogBroadcastHub(max_history=5)
    hub.publish(_entry("i1", level="INFO"))
    hub.publish(_entry("d1", level="DEBUG"))
    hub.publish(_entry("i2", level="INFO"))

    recent = hub.recent(limit=10, min_level="DEBUG")
    assert [entry.message for entry in recent] == ["i1", "d1", "i2"]


def test_queue_full_signals_disconnect_sentinel() -> None:
    """Slow clients must get None so WS can close and reconnect."""
    hub = LogBroadcastHub(max_history=10)
    queue = hub.subscribe(min_level="DEBUG")
    try:
        for index in range(SUBSCRIBER_QUEUE_SIZE):
            hub.publish(_entry(f"fill-{index}"))
        assert queue.qsize() == SUBSCRIBER_QUEUE_SIZE
        assert hub.is_subscribed(queue)

        hub.publish(_entry("overflow"))

        assert not hub.is_subscribed(queue)
        assert queue.qsize() == 1
        assert queue.get_nowait() is None
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


class _Level:
    def __init__(self, name: str) -> None:
        self.name = name


class _File:
    def __init__(self, path: str) -> None:
        self.path = path
        self.name = path.rsplit("/", 1)[-1]


def _record(
    message: str,
    *,
    level: str = "INFO",
    file_path: str = "/app/plugins/live_monitor.py",
) -> dict:
    return {
        "message": message,
        "level": _Level(level),
        "file": _File(file_path),
        "name": "nonebot",
    }


def test_web_filter_drops_matcher_dispatch_info() -> None:
    handled = (
        "Event will be handled by Matcher(type='message', "
        "module=plugins.douyin_link_parser, lineno=45)"
    )
    complete = (
        "Matcher(type='message', module=plugins.douyin_link_parser, "
        "lineno=46) running complete"
    )
    assert web_broadcast_filter(_record(handled)) is False
    assert web_broadcast_filter(_record(complete)) is False


def test_web_filter_drops_inbound_adapter_event_success() -> None:
    colored = (
        "<m>OneBot V11 2706064252</m> | [message.group.normal]: "
        "Message 1767735156 from 120674547@[群:1011952309] '[image]'"
    )
    plain = (
        "OneBot V11 2706064252 | [message.group.normal]: "
        "Message 1767735156 from 120674547@[群:1011952309] '[image]'"
    )
    by_file = _record(
        "ignored body",
        level="SUCCESS",
        file_path="/site-packages/nonebot/message.py",
    )
    assert web_broadcast_filter(_record(colored, level="SUCCESS")) is False
    assert web_broadcast_filter(_record(plain, level="SUCCESS")) is False
    assert web_broadcast_filter(by_file) is False


def test_web_filter_keeps_business_and_startup_logs() -> None:
    assert web_broadcast_filter(_record("NoneBot is initializing...", level="SUCCESS"))
    assert web_broadcast_filter(
        _record("直播开播通知已发送到群组 1011952309", level="SUCCESS")
    )
    assert web_broadcast_filter(
        _record("Running Matcher(type='message') failed.", level="ERROR")
    )
    assert web_broadcast_filter(_record("文件日志已启用: data/logs/cyxcbot.log"))
    assert web_broadcast_filter(
        _record("Checking for matchers in priority 1...", level="DEBUG")
    )
