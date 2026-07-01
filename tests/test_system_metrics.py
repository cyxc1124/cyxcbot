"""Tests for background system metrics sampler (issue #92)."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

import shared.monitor.system_metrics as system_metrics


@pytest.fixture(autouse=True)
def reset_system_metrics_cache():
    system_metrics._cache = None
    system_metrics._sampler_task = None
    yield
    if system_metrics._sampler_task is not None:
        system_metrics._sampler_task.cancel()
        system_metrics._sampler_task = None
    system_metrics._cache = None


def _sample_snapshot() -> system_metrics.SystemMetricsSnapshot:
    return system_metrics.SystemMetricsSnapshot(
        process_cpu_percent=12.3,
        process_memory_mb=256.0,
        cpu_percent=45.6,
        cpu_count=8,
        memory_percent=70.0,
        memory_used_mb=8192.0,
        memory_total_mb=16384.0,
        disk_percent=55.0,
        db_size_mb=1.5,
        log_size_mb=2.5,
        memory_limit_mb=512.0,
        sampled_at=time.monotonic(),
    )


def test_build_payload_reads_cache_without_blocking():
    system_metrics._cache = _sample_snapshot()

    start = time.monotonic()
    payload = system_metrics.build_system_metrics_payload()
    elapsed = time.monotonic() - start

    assert elapsed < 0.05
    assert payload["process_cpu_percent"] == 12.3
    assert payload["cpu_percent"] == 45.6
    assert payload["db_size_mb"] == 1.5
    assert payload["log_size_mb"] == 2.5
    assert payload["memory_limit_mb"] == 512.0


def test_build_payload_falls_back_to_instant_read_when_cache_empty(monkeypatch):
    fake_process = MagicMock()
    fake_process.cpu_percent.return_value = 3.0
    fake_process.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)

    fake_mem = MagicMock(percent=50.0, used=512 * 1024 * 1024, total=1024 * 1024 * 1024)
    fake_disk = MagicMock(percent=60.0)

    monkeypatch.setattr(system_metrics.psutil, "Process", lambda: fake_process)
    monkeypatch.setattr(system_metrics.psutil, "cpu_percent", lambda: 7.0)
    monkeypatch.setattr(system_metrics.psutil, "cpu_count", lambda: 4)
    monkeypatch.setattr(system_metrics.psutil, "virtual_memory", lambda: fake_mem)
    monkeypatch.setattr(system_metrics.psutil, "disk_usage", lambda _: fake_disk)

    payload = system_metrics.build_system_metrics_payload()

    assert payload["process_cpu_percent"] == 3.0
    assert payload["cpu_percent"] == 7.0
    assert payload["cpu_count"] == 4
    assert payload["db_size_mb"] == 0.0
    assert payload["log_size_mb"] == 0.0
    assert payload["memory_limit_mb"] is None


def test_collect_metrics_blocking_includes_storage_probes(monkeypatch):
    monkeypatch.setattr(system_metrics, "CPU_SAMPLE_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(system_metrics, "_get_db_size_mb", lambda: 3.0)
    monkeypatch.setattr(system_metrics, "_get_log_dir_size_mb", lambda: 4.0)
    monkeypatch.setattr(system_metrics, "_get_cgroup_memory_limit_mb", lambda: 128.0)

    fake_process = MagicMock()
    fake_process.cpu_percent.return_value = 10.0
    fake_process.memory_info.return_value = MagicMock(rss=200 * 1024 * 1024)
    fake_mem = MagicMock(percent=50.0, used=512 * 1024 * 1024, total=1024 * 1024 * 1024)
    fake_disk = MagicMock(percent=60.0)

    monkeypatch.setattr(system_metrics.psutil, "Process", lambda: fake_process)
    monkeypatch.setattr(system_metrics.psutil, "cpu_percent", lambda: 20.0)
    monkeypatch.setattr(system_metrics.psutil, "cpu_count", lambda: 2)
    monkeypatch.setattr(system_metrics.psutil, "virtual_memory", lambda: fake_mem)
    monkeypatch.setattr(system_metrics.psutil, "disk_usage", lambda _: fake_disk)

    snap = system_metrics._collect_metrics_blocking()

    assert snap.db_size_mb == 3.0
    assert snap.log_size_mb == 4.0
    assert snap.memory_limit_mb == 128.0


@pytest.mark.asyncio
async def test_sampler_updates_cache(monkeypatch):
    calls = {"count": 0}

    def fake_collect() -> system_metrics.SystemMetricsSnapshot:
        calls["count"] += 1
        return _sample_snapshot()

    monkeypatch.setattr(
        system_metrics,
        "_collect_metrics_blocking",
        fake_collect,
    )
    monkeypatch.setattr(system_metrics, "SAMPLE_INTERVAL_SECONDS", 0.01)

    system_metrics.start_system_metrics_sampler()
    await asyncio.sleep(0.05)
    await system_metrics.stop_system_metrics_sampler()

    assert calls["count"] >= 1
    assert system_metrics.get_cached_snapshot() is not None
    assert system_metrics.get_cached_snapshot().process_cpu_percent == 12.3


@pytest.mark.asyncio
async def test_sampler_keeps_last_good_value_on_failure(monkeypatch):
    system_metrics._cache = _sample_snapshot()
    monkeypatch.setattr(
        system_metrics,
        "_collect_metrics_blocking",
        MagicMock(side_effect=RuntimeError("psutil down")),
    )
    monkeypatch.setattr(system_metrics, "SAMPLE_INTERVAL_SECONDS", 0.01)

    system_metrics.start_system_metrics_sampler()
    await asyncio.sleep(0.05)
    await system_metrics.stop_system_metrics_sampler()

    snap = system_metrics.get_cached_snapshot()
    assert snap is not None
    assert snap.process_cpu_percent == 12.3


@pytest.mark.asyncio
async def test_status_query_does_not_block_event_loop():
    system_metrics._cache = _sample_snapshot()

    delays: list[float] = []

    async def probe() -> None:
        for _ in range(20):
            start = time.monotonic()
            await asyncio.sleep(0)
            delays.append(time.monotonic() - start)

    async def query_status() -> None:
        for _ in range(20):
            system_metrics.build_system_metrics_payload()
            await asyncio.sleep(0)

    await asyncio.gather(probe(), query_status())
    assert max(delays) < 0.05
