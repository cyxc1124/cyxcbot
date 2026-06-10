"""Compute monitor API polling schedules for admin display and runtime scheduling."""

from __future__ import annotations

from typing import Any, Optional

DYNAMIC_MIN_TICK_INTERVAL_SECONDS = 3.0
LIVE_BATCH_REQUEST_GAP_SECONDS = 0.3
LIVE_WEBSOCKET_BACKUP_MIN_INTERVAL_SECONDS = 300


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def compute_dynamic_poll_schedule(
    target_count: int,
    configured_interval_seconds: int,
    *,
    use_stagger: bool = True,
    min_tick_interval_seconds: float = DYNAMIC_MIN_TICK_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Compute dynamic monitor polling schedule for stagger or batch mode."""
    if not use_stagger:
        return _compute_dynamic_batch_poll_schedule(
            target_count,
            configured_interval_seconds,
        )
    return _compute_dynamic_stagger_poll_schedule(
        target_count,
        configured_interval_seconds,
        min_tick_interval_seconds=min_tick_interval_seconds,
    )


def _compute_dynamic_stagger_poll_schedule(
    target_count: int,
    configured_interval_seconds: int,
    *,
    min_tick_interval_seconds: float = DYNAMIC_MIN_TICK_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Stagger one UP per tick; cap tick frequency with a minimum interval."""
    if target_count <= 0:
        return {
            "strategy": "stagger",
            "target_count": 0,
            "configured_interval_seconds": configured_interval_seconds,
            "min_tick_interval_seconds": min_tick_interval_seconds,
            "tick_interval_seconds": 0.0,
            "per_target_cycle_seconds": 0.0,
            "requests_per_second_avg": 0.0,
            "requests_per_second_peak": 0.0,
            "meets_configured_interval": True,
            "warning": None,
        }

    ideal_tick = configured_interval_seconds / target_count
    tick_interval = max(min_tick_interval_seconds, ideal_tick)
    per_target_cycle = tick_interval * target_count
    meets_configured = per_target_cycle <= configured_interval_seconds + 0.01
    peak_rps = 1.0 / tick_interval
    avg_rps = target_count / per_target_cycle

    warning: Optional[str] = None
    if not meets_configured:
        warning = (
            f"当前 {target_count} 个 UP 主较多，每人实际约 "
            f"{per_target_cycle:.0f} 秒检查一次（设置 {configured_interval_seconds} 秒）。"
            f"建议增大检查间隔或减少订阅数量。"
        )

    return {
        "strategy": "stagger",
        "target_count": target_count,
        "configured_interval_seconds": configured_interval_seconds,
        "min_tick_interval_seconds": min_tick_interval_seconds,
        "tick_interval_seconds": _round(tick_interval),
        "per_target_cycle_seconds": _round(per_target_cycle),
        "requests_per_second_avg": _round(avg_rps),
        "requests_per_second_peak": _round(peak_rps),
        "meets_configured_interval": meets_configured,
        "warning": warning,
    }


def _compute_dynamic_batch_poll_schedule(
    target_count: int,
    configured_interval_seconds: int,
) -> dict[str, Any]:
    """Batch mode: check all UPs sequentially every configured interval."""
    poll_interval = configured_interval_seconds

    if target_count <= 0:
        return {
            "strategy": "batch",
            "target_count": 0,
            "configured_interval_seconds": configured_interval_seconds,
            "poll_interval_seconds": poll_interval,
            "tick_interval_seconds": 0.0,
            "per_target_cycle_seconds": 0.0,
            "requests_per_second_avg": 0.0,
            "requests_per_second_peak": 0.0,
            "meets_configured_interval": True,
            "warning": None,
        }

    avg_rps = target_count / poll_interval
    peak_rps = 1.0

    warning: Optional[str] = None
    if target_count >= 5:
        warning = (
            f"批量模式下每 {poll_interval} 秒会依次检查全部 {target_count} 个 UP 主。"
            f"订阅较多时建议启用分散检查以降低 API 峰值压力。"
        )

    return {
        "strategy": "batch",
        "target_count": target_count,
        "configured_interval_seconds": configured_interval_seconds,
        "poll_interval_seconds": poll_interval,
        "tick_interval_seconds": _round(poll_interval),
        "per_target_cycle_seconds": _round(poll_interval),
        "requests_per_second_avg": _round(avg_rps),
        "requests_per_second_peak": _round(peak_rps),
        "meets_configured_interval": True,
        "warning": warning,
    }


def compute_live_poll_schedule(
    target_count: int,
    configured_interval_seconds: int,
    *,
    use_websocket: bool,
    batch_gap_seconds: float = LIVE_BATCH_REQUEST_GAP_SECONDS,
) -> dict[str, Any]:
    """Live monitor: WebSocket primary; API batch poll as backup or sole mode."""
    if use_websocket:
        poll_interval = max(
            LIVE_WEBSOCKET_BACKUP_MIN_INTERVAL_SECONDS,
            configured_interval_seconds * 5,
        )
        strategy = "websocket_primary"
    else:
        poll_interval = configured_interval_seconds
        strategy = "batch"

    if target_count <= 0:
        return {
            "strategy": strategy,
            "target_count": 0,
            "configured_interval_seconds": configured_interval_seconds,
            "poll_interval_seconds": poll_interval,
            "batch_gap_seconds": batch_gap_seconds,
            "use_websocket": use_websocket,
            "tick_interval_seconds": 0.0,
            "per_target_cycle_seconds": 0.0,
            "requests_per_second_avg": 0.0,
            "requests_per_second_peak": 0.0,
            "meets_configured_interval": True,
            "warning": None,
        }

    burst_duration = batch_gap_seconds * max(0, target_count - 1)
    peak_rps = 1.0 / batch_gap_seconds
    avg_rps = target_count / poll_interval
    per_target_cycle = poll_interval

    warning: Optional[str] = None
    if not use_websocket and peak_rps >= 2.0:
        warning = (
            f"未启用 WebSocket 时，每 {poll_interval} 秒会集中轮询 {target_count} 个房间，"
            f"峰值约 {peak_rps:.1f} 次/秒。建议启用 WebSocket 或增大检查间隔。"
        )
    elif use_websocket and target_count > 0 and peak_rps >= 2.0:
        warning = (
            f"API 备用轮询每 {poll_interval} 秒执行一次，峰值约 {peak_rps:.1f} 次/秒"
            f"（持续约 {burst_duration:.1f} 秒）。"
        )

    return {
        "strategy": strategy,
        "target_count": target_count,
        "configured_interval_seconds": configured_interval_seconds,
        "poll_interval_seconds": poll_interval,
        "batch_gap_seconds": batch_gap_seconds,
        "use_websocket": use_websocket,
        "tick_interval_seconds": _round(batch_gap_seconds),
        "per_target_cycle_seconds": _round(per_target_cycle),
        "requests_per_second_avg": _round(avg_rps),
        "requests_per_second_peak": _round(peak_rps),
        "meets_configured_interval": True,
        "warning": warning,
    }
