"""Tests for shared monitor poll schedule helpers."""

from __future__ import annotations

import pytest

from shared.monitor.poll_schedule import (
    LIVE_BATCH_REQUEST_GAP_SECONDS,
    LIVE_DANMAKU_CLIENT_START_GAP_SECONDS,
    LIVE_POLL_MISFIRE_GRACE_TIME_SECONDS,
    LIVE_WEBSOCKET_BACKUP_MIN_INTERVAL_SECONDS,
    compute_live_poll_schedule,
    resolve_live_poll_interval_seconds,
)


@pytest.mark.parametrize(
    ("configured_interval", "use_websocket", "expected_poll_interval"),
    [
        (60, True, LIVE_WEBSOCKET_BACKUP_MIN_INTERVAL_SECONDS),
        (80, True, 400),
        (120, False, 120),
    ],
)
def test_resolve_live_poll_interval_matches_compute_live_poll_schedule(
    configured_interval: int,
    use_websocket: bool,
    expected_poll_interval: int,
) -> None:
    schedule = compute_live_poll_schedule(
        3,
        configured_interval,
        use_websocket=use_websocket,
    )
    assert (
        resolve_live_poll_interval_seconds(
            configured_interval,
            use_websocket=use_websocket,
        )
        == expected_poll_interval
    )
    assert schedule["poll_interval_seconds"] == expected_poll_interval


def test_compute_live_poll_schedule_websocket_backup_floor() -> None:
    schedule = compute_live_poll_schedule(2, 30, use_websocket=True)
    assert schedule["strategy"] == "websocket_primary"
    assert (
        schedule["poll_interval_seconds"] == LIVE_WEBSOCKET_BACKUP_MIN_INTERVAL_SECONDS
    )
    assert schedule["batch_gap_seconds"] == LIVE_BATCH_REQUEST_GAP_SECONDS


def test_compute_live_poll_schedule_batch_mode_uses_configured_interval() -> None:
    schedule = compute_live_poll_schedule(5, 90, use_websocket=False)
    assert schedule["strategy"] == "batch"
    assert schedule["poll_interval_seconds"] == 90
    assert schedule["requests_per_second_peak"] == pytest.approx(
        round(1.0 / LIVE_BATCH_REQUEST_GAP_SECONDS, 2)
    )


def test_live_runtime_timing_constants() -> None:
    assert LIVE_DANMAKU_CLIENT_START_GAP_SECONDS == 1.0
    assert LIVE_POLL_MISFIRE_GRACE_TIME_SECONDS == 60
