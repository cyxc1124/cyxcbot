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


def test_find_cgroup_value_skips_max_and_missing(tmp_path):
    unlimited = tmp_path / "memory.max"
    unlimited.write_text("max")
    value, path = system_metrics._find_cgroup_value(
        [str(unlimited), str(tmp_path / "does-not-exist")]
    )
    assert value is None
    assert path is None


def test_find_cgroup_value_skip_if_ge_continues_to_next_pattern(tmp_path):
    """回归测试：根 cgroup 的"无限制"哨兵值不应挡住后续更具体的路径。"""
    unlimited_root = tmp_path / "root_limit"
    unlimited_root.write_text("999999999999999")
    real_limit = tmp_path / "slice_limit"
    real_limit.write_text("1000")

    value, path = system_metrics._find_cgroup_value(
        [str(unlimited_root), str(real_limit)], skip_if_ge=1_000_000_000
    )
    assert value == 1000
    assert path == str(real_limit)


def test_find_cgroup_value_skip_if_ge_returns_none_when_all_skipped(tmp_path):
    unlimited_root = tmp_path / "root_limit"
    unlimited_root.write_text("999999999999999")

    value, path = system_metrics._find_cgroup_value(
        [str(unlimited_root)], skip_if_ge=1_000_000_000
    )
    assert value is None
    assert path is None


def test_get_cgroup_memory_limit_mb_uses_wide_search(monkeypatch):
    monkeypatch.setattr(
        system_metrics,
        "_find_cgroup_value",
        lambda patterns, **kwargs: (512 * 1024**2, "/x"),
    )
    assert system_metrics._get_cgroup_memory_limit_mb() == 512.0


def test_get_cgroup_memory_limit_mb_skips_unlimited_root_and_finds_slice_value(
    tmp_path, monkeypatch
):
    """issue 回归测试：根路径读到"无限制"哨兵值时，应继续尝试更具体的
    本进程专属 slice 路径，而不是直接判定为无限制。"""
    root = tmp_path / "memory.limit_in_bytes"
    root.write_text(str(2 * system_metrics._CGROUP_UNLIMITED_THRESHOLD_BYTES))

    slice_file = tmp_path / "kubepods.slice" / "pod-abc" / "memory.limit_in_bytes"
    slice_file.parent.mkdir(parents=True)
    slice_file.write_text(str(512 * 1024**2))

    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(
        system_metrics,
        "_CGROUP_MEMORY_LIMIT_PATTERNS",
        [str(root), str(slice_file)],
    )

    assert system_metrics._get_cgroup_memory_limit_mb() == pytest.approx(512.0)


def test_get_cgroup_memory_limit_mb_none_when_all_candidates_unlimited(
    tmp_path, monkeypatch
):
    root = tmp_path / "memory.limit_in_bytes"
    root.write_text(str(2 * system_metrics._CGROUP_UNLIMITED_THRESHOLD_BYTES))
    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(system_metrics, "_CGROUP_MEMORY_LIMIT_PATTERNS", [str(root)])

    assert system_metrics._get_cgroup_memory_limit_mb() is None


def test_get_cgroup_memory_limit_mb_preserves_legitimate_1tib_limit(
    tmp_path, monkeypatch
):
    """issue 回归测试：显式配置的 1 TiB（甚至更大）限制是合法值，不应被当成
    "无限制"哨兵值跳过——阈值必须紧贴内核哨兵本身，而不是 1 TiB 这类整数。"""
    limit_file = tmp_path / "memory.limit_in_bytes"
    one_tib = 1024**4
    limit_file.write_text(str(one_tib))

    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(
        system_metrics, "_CGROUP_MEMORY_LIMIT_PATTERNS", [str(limit_file)]
    )

    assert system_metrics._get_cgroup_memory_limit_mb() == pytest.approx(
        one_tib / (1024**2)
    )


def test_get_cgroup_memory_limit_mb_still_skips_real_kernel_sentinel(
    tmp_path, monkeypatch
):
    """回归测试：阈值调整后，真正的内核哨兵值（LLONG_MAX 页对齐）依然要被
    识别为"未设置限制"，不能因为放宽了 1 TiB 就连哨兵本身也放过。"""
    limit_file = tmp_path / "memory.limit_in_bytes"
    limit_file.write_text(str(system_metrics._CGROUP_UNLIMITED_THRESHOLD_BYTES))

    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(
        system_metrics, "_CGROUP_MEMORY_LIMIT_PATTERNS", [str(limit_file)]
    )

    assert system_metrics._get_cgroup_memory_limit_mb() is None


def test_own_cgroup_subpath_parses_v1_memory_line(tmp_path, monkeypatch):
    proc_self_cgroup = tmp_path / "cgroup"
    proc_self_cgroup.write_text(
        "11:memory:/kubepods.slice/kubepods-podx.slice/docker-abc.scope\n"
        "10:cpu,cpuacct:/kubepods.slice/kubepods-podx.slice/docker-abc.scope\n"
    )
    monkeypatch.setattr(system_metrics, "_PROC_SELF_CGROUP_PATH", str(proc_self_cgroup))

    assert (
        system_metrics._own_cgroup_subpath("memory")
        == "kubepods.slice/kubepods-podx.slice/docker-abc.scope"
    )


def test_own_cgroup_subpath_parses_v2_unified_line(tmp_path, monkeypatch):
    proc_self_cgroup = tmp_path / "cgroup"
    proc_self_cgroup.write_text(
        "0::/kubepods.slice/kubepods-pody.slice/crio-def.scope\n"
    )
    monkeypatch.setattr(system_metrics, "_PROC_SELF_CGROUP_PATH", str(proc_self_cgroup))

    assert (
        system_metrics._own_cgroup_subpath("memory")
        == "kubepods.slice/kubepods-pody.slice/crio-def.scope"
    )


def test_own_cgroup_subpath_returns_none_when_at_namespace_root(tmp_path, monkeypatch):
    """已启用 cgroup namespace 隔离时，本进程看到的路径就是"/"，此时根路径
    本身即本进程的 cgroup，无需（也无法）派生更具体的子路径。"""
    proc_self_cgroup = tmp_path / "cgroup"
    proc_self_cgroup.write_text("0::/\n")
    monkeypatch.setattr(system_metrics, "_PROC_SELF_CGROUP_PATH", str(proc_self_cgroup))

    assert system_metrics._own_cgroup_subpath("memory") is None


def test_own_cgroup_subpath_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        system_metrics, "_PROC_SELF_CGROUP_PATH", str(tmp_path / "does-not-exist")
    )
    assert system_metrics._own_cgroup_subpath("memory") is None


def test_own_cgroup_memory_limit_candidates_prepends_derived_path(monkeypatch):
    monkeypatch.setattr(
        system_metrics,
        "_own_cgroup_subpath",
        lambda controller: "kubepods.slice/pod-x",
    )
    candidates = system_metrics._own_cgroup_memory_limit_candidates()

    assert candidates[:2] == [
        "/sys/fs/cgroup/memory/kubepods.slice/pod-x/memory.limit_in_bytes",
        "/sys/fs/cgroup/kubepods.slice/pod-x/memory.max",
    ]
    assert candidates[2:] == system_metrics._CGROUP_MEMORY_LIMIT_PATTERNS


def test_own_cgroup_memory_limit_candidates_falls_back_to_root_only(monkeypatch):
    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    candidates = system_metrics._own_cgroup_memory_limit_candidates()

    assert candidates == system_metrics._CGROUP_MEMORY_LIMIT_PATTERNS


def test_sibling_cgroup_usage_path_v1_and_v2():
    assert (
        system_metrics._sibling_cgroup_usage_path(
            "/sys/fs/cgroup/memory/kubepods.slice/pod-x/memory.limit_in_bytes"
        )
        == "/sys/fs/cgroup/memory/kubepods.slice/pod-x/memory.usage_in_bytes"
    )
    assert (
        system_metrics._sibling_cgroup_usage_path("/sys/fs/cgroup/memory.max")
        == "/sys/fs/cgroup/memory.current"
    )
    assert system_metrics._sibling_cgroup_usage_path("/weird/path/other") is None


def test_get_container_memory_info_requires_usage_in_same_directory(
    tmp_path, monkeypatch
):
    """限制文件命中，但同目录下没有对应的用量文件时应放弃，而不是去别处找。"""
    limit_file = tmp_path / "memory.limit_in_bytes"
    limit_file.write_text(str(2 * 1024**3))

    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(
        system_metrics, "_CGROUP_MEMORY_LIMIT_PATTERNS", [str(limit_file)]
    )
    assert system_metrics.get_container_memory_info() is None


def test_get_container_memory_info_returns_usage_percent(tmp_path, monkeypatch):
    limit_file = tmp_path / "memory.limit_in_bytes"
    limit_file.write_text(str(2 * 1024**3))
    usage_file = tmp_path / "memory.usage_in_bytes"
    usage_file.write_text(str(1 * 1024**3))

    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(
        system_metrics, "_CGROUP_MEMORY_LIMIT_PATTERNS", [str(limit_file)]
    )

    info = system_metrics.get_container_memory_info()
    assert info is not None
    assert info["total_gb"] == pytest.approx(2.0)
    assert info["used_gb"] == pytest.approx(1.0)
    assert info["percent"] == pytest.approx(50.0)
    assert info["limit_file"] == str(limit_file)
    assert info["usage_file"] == str(usage_file)


def test_get_container_memory_info_skips_unlimited_root_limit(tmp_path, monkeypatch):
    """issue 回归测试：get_container_memory_info 同样不应被根路径的
    "无限制"哨兵值挡住，需继续搜索到本进程专属 slice 里的真实限制。"""
    root_limit = tmp_path / "memory.limit_in_bytes"
    root_limit.write_text(str(2 * system_metrics._CGROUP_UNLIMITED_THRESHOLD_BYTES))

    slice_dir = tmp_path / "kubepods.slice" / "pod-abc"
    slice_dir.mkdir(parents=True)
    (slice_dir / "memory.limit_in_bytes").write_text(str(2 * 1024**3))
    (slice_dir / "memory.usage_in_bytes").write_text(str(1 * 1024**3))

    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(
        system_metrics,
        "_CGROUP_MEMORY_LIMIT_PATTERNS",
        [str(root_limit), str(slice_dir / "memory.limit_in_bytes")],
    )

    info = system_metrics.get_container_memory_info()
    assert info is not None
    assert info["total_gb"] == pytest.approx(2.0)
    assert info["used_gb"] == pytest.approx(1.0)


def test_get_container_memory_info_does_not_pair_usage_from_root(tmp_path, monkeypatch):
    """issue 回归测试：即便根目录也有一份用量文件，也绝不能把它和 slice
    的限制值配对——那会算出跨容器/宿主机的错误百分比。"""
    root_limit = tmp_path / "memory.limit_in_bytes"
    root_limit.write_text(str(2 * system_metrics._CGROUP_UNLIMITED_THRESHOLD_BYTES))
    # 根目录（宿主机整体）用量远大于 slice 限制，若被错误配对会得到 >100% 用量
    (tmp_path / "memory.usage_in_bytes").write_text(str(50 * 1024**3))

    slice_dir = tmp_path / "kubepods.slice" / "pod-abc"
    slice_dir.mkdir(parents=True)
    (slice_dir / "memory.limit_in_bytes").write_text(str(2 * 1024**3))
    (slice_dir / "memory.usage_in_bytes").write_text(str(1 * 1024**3))

    monkeypatch.setattr(system_metrics, "_own_cgroup_subpath", lambda controller: None)
    monkeypatch.setattr(
        system_metrics,
        "_CGROUP_MEMORY_LIMIT_PATTERNS",
        [str(root_limit), str(slice_dir / "memory.limit_in_bytes")],
    )

    info = system_metrics.get_container_memory_info()
    assert info is not None
    assert info["used_gb"] == pytest.approx(1.0)
    assert info["percent"] == pytest.approx(50.0)
    assert 0 <= info["percent"] <= 100
    assert info["available_gb"] >= 0


def test_get_container_memory_info_uses_own_cgroup_not_sibling_pod(
    tmp_path, monkeypatch
):
    """issue 回归测试：未做 cgroup namespace 隔离的宿主机上，kubepods.slice
    下会并列存在其他 Pod/容器的目录；即使它们先被枚举到，也必须只使用
    /proc/self/cgroup 推导出的本进程自己的目录，而不是随便一个兄弟目录。"""
    memory_root = tmp_path / "memory"
    other_pod = memory_root / "kubepods.slice" / "aaaa-other-pod"
    own_pod = memory_root / "kubepods.slice" / "zzzz-own-pod"
    other_pod.mkdir(parents=True)
    own_pod.mkdir(parents=True)
    # 兄弟 Pod 排在字母序更前面，若按枚举顺序取第一个会错误地读到它
    (other_pod / "memory.limit_in_bytes").write_text(str(8 * 1024**3))
    (other_pod / "memory.usage_in_bytes").write_text(str(6 * 1024**3))
    (own_pod / "memory.limit_in_bytes").write_text(str(1 * 1024**3))
    (own_pod / "memory.usage_in_bytes").write_text(str(256 * 1024**2))

    monkeypatch.setattr(system_metrics, "_CGROUP_V1_MEMORY_ROOT", str(memory_root))
    monkeypatch.setattr(system_metrics, "_CGROUP_UNIFIED_ROOT", str(tmp_path))
    monkeypatch.setattr(
        system_metrics,
        "_own_cgroup_subpath",
        lambda controller: "kubepods.slice/zzzz-own-pod",
    )
    monkeypatch.setattr(system_metrics, "_CGROUP_MEMORY_LIMIT_PATTERNS", [])

    info = system_metrics.get_container_memory_info()
    assert info is not None
    assert info["total_gb"] == pytest.approx(1.0)
    assert info["used_gb"] == pytest.approx(0.25)
    assert info["limit_file"] == str(own_pod / "memory.limit_in_bytes")


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
