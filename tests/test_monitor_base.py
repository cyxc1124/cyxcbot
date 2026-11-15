"""Tests for the shared monitor polling / delivery mixins."""

from __future__ import annotations

import asyncio

import pytest

from shared.monitor.base import (
    DeliveryGuardMixin,
    PollingMonitorMixin,
    StaggeredPollingMixin,
)
from shared.monitor.check_cycle import CheckCycleLogger


class _Poller(StaggeredPollingMixin):
    _monitor_label = "测试监控"

    def __init__(self, ids: list[str], failing: set[str] | None = None):
        self.ids = ids
        self.failing = failing or set()
        self.checked: list[str] = []
        self.is_running = True
        self.last_check_at = None
        self._stagger_index = 0
        self._cycle_logger = CheckCycleLogger("测试监控")

    def _target_ids(self) -> list[str]:
        return list(self.ids)

    async def _check_target(self, target_id: str) -> bool:
        self.checked.append(target_id)
        if target_id == "boom":
            raise RuntimeError("boom")
        return target_id not in self.failing


@pytest.mark.asyncio
async def test_stagger_checks_one_target_per_tick_and_wraps():
    monitor = _Poller(["a", "b"])
    for _ in range(3):
        await monitor._check_next_target()
    assert monitor.checked == ["a", "b", "a"]
    assert monitor.last_check_at is not None


@pytest.mark.asyncio
async def test_stagger_resets_index_when_targets_shrink():
    monitor = _Poller(["a", "b", "c"])
    monitor._stagger_index = 2
    monitor.ids = ["a"]
    await monitor._check_next_target()
    assert monitor.checked == ["a"]


@pytest.mark.asyncio
async def test_stopped_monitor_skips_all_check_paths():
    monitor = _Poller(["a"])
    monitor.is_running = False
    await monitor._check_next_target()
    await monitor._check_all_targets()
    assert await monitor.run_manual_check() == {"checked": [], "failed": []}
    assert monitor.checked == []


@pytest.mark.asyncio
async def test_batch_check_records_failures_and_errors():
    monitor = _Poller(["a", "bad", "boom"], failing={"bad"})
    summarized: list[list[str]] = []
    monitor._cycle_logger.emit_summary = lambda: summarized.append(  # type: ignore[method-assign]
        monitor._cycle_logger.failure_ids
    )
    await monitor._check_all_targets()
    assert sorted(monitor.checked) == ["a", "bad", "boom"]
    assert summarized == [["bad", "boom"]]


@pytest.mark.asyncio
async def test_manual_check_splits_checked_and_failed():
    monitor = _Poller(["a", "bad", "boom"], failing={"bad"})
    result = await monitor.run_manual_check()
    assert result == {"checked": ["a"], "failed": ["bad", "boom"]}
    assert await monitor.run_manual_check(["a"]) == {"checked": ["a"], "failed": []}


class _Guard(DeliveryGuardMixin):
    _delivery_task_name = "测试投递"

    def __init__(self):
        self.active = {"x"}
        self._check_generation = {}
        self._delivery_tasks = set()

    def _is_active_target(self, target_id: str) -> bool:
        return target_id in self.active


def test_check_generation_invalidates_after_bump_or_removal():
    guard = _Guard()
    assert guard._check_still_valid("x", 0)
    guard._bump_check_generation("x")
    assert not guard._check_still_valid("x", 0)
    assert guard._check_still_valid("x", 1)
    guard.active.clear()
    assert not guard._check_still_valid("x", 1)


@pytest.mark.asyncio
async def test_drain_waits_for_spawned_delivery_tasks():
    guard = _Guard()
    done: list[int] = []

    async def deliver():
        await asyncio.sleep(0)
        done.append(1)

    guard._spawn_delivery_task(deliver())
    await guard._drain_pending_deliveries()
    assert done == [1]
    assert not guard._delivery_tasks


def test_stagger_is_opt_in():
    assert not hasattr(PollingMonitorMixin, "_check_next_target")
    assert hasattr(StaggeredPollingMixin, "_check_next_target")
