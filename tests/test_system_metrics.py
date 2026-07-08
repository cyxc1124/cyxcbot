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


def test_find_cgroup_value_matches_plain_path(tmp_path):
    f = tmp_path / "memory.max"
    f.write_text("12345\n")
    value, path = system_metrics._find_cgroup_value([str(f)])
    assert value == 12345
    assert path == str(f)


def test_find_cgroup_value_matches_glob_pattern(tmp_path):
    slice_dir = tmp_path / "kubepods.slice" / "podabc"
    slice_dir.mkdir(parents=True)
    (slice_dir / "memory.limit_in_bytes").write_text("999")
    pattern = str(tmp_path / "kubepods.slice" / "*" / "memory.limit_in_bytes")
    value, path = system_metrics._find_cgroup_value([pattern])
    assert value == 999
    assert path.endswith("memory.limit_in_bytes")


def test_find_cgroup_value_skips_max_and_missing(tmp_path):
    unlimited = tmp_path / "memory.max"
    unlimited.write_text("max")
    value, path = system_metrics._find_cgroup_value(
        [str(unlimited), str(tmp_path / "does-not-exist")]
    )
    assert value is None
    assert path is None


def test_get_cgroup_memory_limit_mb_uses_wide_search(monkeypatch):
    monkeypatch.setattr(
        system_metrics, "_find_cgroup_value", lambda patterns: (512 * 1024**2, "/x")
    )
    assert system_metrics._get_cgroup_memory_limit_mb() == 512.0


def test_get_cgroup_memory_limit_mb_treats_huge_value_as_unlimited(monkeypatch):
    monkeypatch.setattr(
        system_metrics,
        "_find_cgroup_value",
        lambda patterns: (2 * system_metrics._CGROUP_UNLIMITED_THRESHOLD_BYTES, "/x"),
    )
    assert system_metrics._get_cgroup_memory_limit_mb() is None


def test_get_container_memory_info_requires_both_limit_and_usage(monkeypatch):
    def fake_find(patterns):
        if patterns is system_metrics._CGROUP_MEMORY_LIMIT_PATTERNS:
            return 2 * 1024**3, "/limit"
        return None, None

    monkeypatch.setattr(system_metrics, "_find_cgroup_value", fake_find)
    assert system_metrics.get_container_memory_info() is None


def test_get_container_memory_info_returns_usage_percent(monkeypatch):
    def fake_find(patterns):
        if patterns is system_metrics._CGROUP_MEMORY_LIMIT_PATTERNS:
            return 2 * 1024**3, "/limit"
        return 1 * 1024**3, "/usage"

    monkeypatch.setattr(system_metrics, "_find_cgroup_value", fake_find)
    info = system_metrics.get_container_memory_info()
    assert info is not None
    assert info["total_gb"] == pytest.approx(2.0)
    assert info["used_gb"] == pytest.approx(1.0)
    assert info["percent"] == pytest.approx(50.0)
    assert info["limit_file"] == "/limit"
    assert info["usage_file"] == "/usage"


def test_detect_container_environment_kubernetes(monkeypatch):
    monkeypatch.setattr(system_metrics, "_DOCKERENV_PATH", "/does/not/exist")
    monkeypatch.setattr(system_metrics, "_PROC_1_CGROUP_PATH", "/does/not/exist")
    monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")

    env = system_metrics.detect_container_environment()
    assert env["is_kubernetes"] is True
    assert env["is_container"] is True
    assert env["container_type"] == "Kubernetes Pod"


def test_detect_container_environment_docker_env_var(monkeypatch):
    monkeypatch.setattr(system_metrics, "_DOCKERENV_PATH", "/does/not/exist")
    monkeypatch.setattr(system_metrics, "_PROC_1_CGROUP_PATH", "/does/not/exist")
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    monkeypatch.setenv("DOCKER_CONTAINER", "true")

    env = system_metrics.detect_container_environment()
    assert env["is_docker"] is True
    assert env["container_type"] == "Docker Container"


def test_detect_container_environment_bare_metal(monkeypatch):
    monkeypatch.setattr(system_metrics, "_DOCKERENV_PATH", "/does/not/exist")
    monkeypatch.setattr(system_metrics, "_PROC_1_CGROUP_PATH", "/does/not/exist")
    monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)

    env = system_metrics.detect_container_environment()
    assert env["is_container"] is False
    assert env["container_type"] == "Physical/VM"


def test_get_container_cpu_limit_reads_cgroup_v2(tmp_path, monkeypatch):
    cpu_max = tmp_path / "cpu.max"
    cpu_max.write_text("50000 100000")
    monkeypatch.setattr(system_metrics, "_CGROUP_CPU_QUOTA_PATHS", [str(cpu_max)])
    monkeypatch.setattr(system_metrics, "_CGROUP_CPU_PERIOD_PATHS", [str(cpu_max)])

    assert system_metrics.get_container_cpu_limit() == pytest.approx(0.5)


def test_get_container_cpu_limit_unset_returns_none(tmp_path, monkeypatch):
    cpu_max = tmp_path / "cpu.max"
    cpu_max.write_text("max 100000")
    monkeypatch.setattr(system_metrics, "_CGROUP_CPU_QUOTA_PATHS", [str(cpu_max)])
    monkeypatch.setattr(system_metrics, "_CGROUP_CPU_PERIOD_PATHS", [str(cpu_max)])

    assert system_metrics.get_container_cpu_limit() is None


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
