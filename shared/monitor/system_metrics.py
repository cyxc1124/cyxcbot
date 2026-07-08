"""Background system metrics sampler with in-memory cache (issue #92)."""

from __future__ import annotations

import asyncio
import glob
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
from nonebot.log import logger

from shared.monitor.background_task import spawn_background_task

SAMPLE_INTERVAL_SECONDS = 5.0
CPU_SAMPLE_INTERVAL_SECONDS = 1.0

# cgroup v1/v2 及 Docker/Kubernetes 常见 slice 路径（含通配符）
_CGROUP_MEMORY_LIMIT_PATTERNS = [
    "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    "/sys/fs/cgroup/memory.max",
    "/sys/fs/cgroup/memory/kubepods*/memory.limit_in_bytes",
    "/sys/fs/cgroup/memory/kubepods.slice/*/memory.limit_in_bytes",
    "/sys/fs/cgroup/memory/docker/*/memory.limit_in_bytes",
    "/sys/fs/cgroup/memory/system.slice/*/memory.limit_in_bytes",
]
_CGROUP_MEMORY_USAGE_PATTERNS = [
    "/sys/fs/cgroup/memory/memory.usage_in_bytes",
    "/sys/fs/cgroup/memory.current",
    "/sys/fs/cgroup/memory/kubepods*/memory.usage_in_bytes",
    "/sys/fs/cgroup/memory/kubepods.slice/*/memory.usage_in_bytes",
    "/sys/fs/cgroup/memory/docker/*/memory.usage_in_bytes",
    "/sys/fs/cgroup/memory/system.slice/*/memory.usage_in_bytes",
]
# 大于 1TB 的 cgroup v1 限制值视为"未设置限制"（内核默认填充的巨大数字）
_CGROUP_UNLIMITED_THRESHOLD_BYTES = 1024**4

_DOCKERENV_PATH = "/.dockerenv"
_PROC_1_CGROUP_PATH = "/proc/1/cgroup"
_CGROUP_CPU_QUOTA_PATHS = [
    "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
    "/sys/fs/cgroup/cpu.max",  # cgroup v2
]
_CGROUP_CPU_PERIOD_PATHS = [
    "/sys/fs/cgroup/cpu/cpu.cfs_period_us",
    "/sys/fs/cgroup/cpu.max",  # cgroup v2 (同一文件，不同格式)
]

_cache: SystemMetricsSnapshot | None = None
_sampler_task: asyncio.Task[None] | None = None


@dataclass(frozen=True)
class SystemMetricsSnapshot:
    process_cpu_percent: float
    process_memory_mb: float
    cpu_percent: float
    cpu_count: int
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    db_size_mb: float
    log_size_mb: float
    memory_limit_mb: float | None
    sampled_at: float


def get_cached_snapshot() -> SystemMetricsSnapshot | None:
    return _cache


def _get_db_size_mb() -> float:
    db_url = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///data/cyxcbot.db")
    if "sqlite" not in db_url:
        return 0.0
    path = db_url.split(":///")[-1].split("?")[0]
    db_path = Path(path) if Path(path).is_absolute() else Path.cwd() / path
    if not db_path.exists():
        return 0.0
    try:
        return db_path.stat().st_size / (1024**2)
    except OSError:
        return 0.0


def _get_log_dir_size_mb() -> float:
    log_pattern = os.getenv("LOG_FILE_PATH", "data/logs/cyxcbot.log")
    log_dir = Path(log_pattern).parent
    if not log_dir.is_absolute():
        log_dir = Path.cwd() / log_dir
    if not log_dir.is_dir():
        return 0.0
    try:
        total = sum(f.stat().st_size for f in log_dir.iterdir() if f.is_file())
        return total / (1024**2)
    except OSError:
        return 0.0


def detect_container_environment() -> dict[str, Any]:
    """检测容器环境（Docker / Kubernetes）。"""
    is_docker = (
        os.path.exists(_DOCKERENV_PATH)
        or os.getenv("DOCKER_CONTAINER", "").lower() == "true"
    )
    is_kubernetes = any(key.startswith(("KUBERNETES_", "KUBE_")) for key in os.environ)

    try:
        cgroup_info = Path(_PROC_1_CGROUP_PATH).read_text()
        if "docker" in cgroup_info or "kubepods" in cgroup_info:
            is_docker = True
    except OSError:
        pass

    return {
        "is_container": is_docker or is_kubernetes,
        "is_docker": is_docker,
        "is_kubernetes": is_kubernetes,
        "container_type": "Kubernetes Pod"
        if is_kubernetes
        else ("Docker Container" if is_docker else "Physical/VM"),
    }


def _find_cgroup_value(
    patterns: list[str], *, skip_if_ge: int | None = None
) -> tuple[int | None, str | None]:
    """按路径模式（支持通配符）查找第一个有效的 cgroup 数值文件，返回 (数值, 命中路径)。

    根路径（如 `/sys/fs/cgroup/memory/memory.limit_in_bytes`）在未做 cgroup
    namespace 隔离的环境下几乎总是存在，其"无限制"哨兵值是一个巨大的合法数字，
    并非 `max` 字符串。若 `skip_if_ge` 给定，命中值达到该阈值时视为"此路径未设置"，
    跳过并继续尝试后续（更具体的 kubepods/docker slice）路径，而不是直接返回。
    """
    for pattern in patterns:
        candidates = glob.glob(pattern) if "*" in pattern else [pattern]
        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                content = Path(path).read_text().strip()
            except OSError:
                continue
            if content == "max" or not content.isdigit():
                continue
            value = int(content)
            if skip_if_ge is not None and value >= skip_if_ge:
                continue
            return value, path
    return None, None


def _get_cgroup_memory_limit_mb() -> float | None:
    limit_bytes, _ = _find_cgroup_value(
        _CGROUP_MEMORY_LIMIT_PATTERNS, skip_if_ge=_CGROUP_UNLIMITED_THRESHOLD_BYTES
    )
    if limit_bytes is None:
        return None
    return limit_bytes / (1024**2)


def get_container_memory_info() -> dict[str, Any] | None:
    """获取容器内存信息（cgroup 限制 + 用量），用于 `/status` 等展示场景。"""
    try:
        limit_bytes, limit_file = _find_cgroup_value(
            _CGROUP_MEMORY_LIMIT_PATTERNS, skip_if_ge=_CGROUP_UNLIMITED_THRESHOLD_BYTES
        )
        usage_bytes, usage_file = _find_cgroup_value(_CGROUP_MEMORY_USAGE_PATTERNS)

        if limit_bytes is None or usage_bytes is None:
            logger.debug(
                "未找到有效的容器内存信息: limit_bytes={}, usage_bytes={}",
                limit_bytes,
                usage_bytes,
            )
            return None

        limit_gb = limit_bytes / (1024**3)
        usage_gb = usage_bytes / (1024**3)
        available_gb = limit_gb - usage_gb
        usage_percent = (usage_gb / limit_gb) * 100

        logger.debug(
            "成功读取容器内存: 限制={:.1f}GB, 使用={:.1f}GB (来源: {})",
            limit_gb,
            usage_gb,
            limit_file,
        )

        return {
            "used_gb": usage_gb,
            "total_gb": limit_gb,
            "available_gb": available_gb,
            "percent": usage_percent,
            "is_container": True,
            "limit_file": limit_file,
            "usage_file": usage_file,
        }
    except Exception as e:
        logger.debug("容器内存检测异常: {}", e)
        return None


def get_container_cpu_limit() -> float | None:
    """获取容器 CPU 限制信息（以核心数表示）。"""
    try:
        quota = None
        period = None

        for quota_file in _CGROUP_CPU_QUOTA_PATHS:
            if not os.path.exists(quota_file):
                continue
            try:
                content = Path(quota_file).read_text().strip()
                if quota_file.endswith("cpu.max"):  # cgroup v2
                    parts = content.split()
                    if len(parts) >= 2 and parts[0] != "max":
                        quota = int(parts[0])
                        period = int(parts[1])
                        break
                elif content != "-1" and content.isdigit():  # cgroup v1
                    quota = int(content)
            except OSError, ValueError:
                continue

        if quota and not period:
            for period_file in _CGROUP_CPU_PERIOD_PATHS:
                if not os.path.exists(period_file):
                    continue
                try:
                    content = Path(period_file).read_text().strip()
                    if content.isdigit():
                        period = int(content)
                        break
                except OSError, ValueError:
                    continue

        if quota and period and quota > 0:
            return quota / period
    except Exception as e:
        logger.debug("读取容器CPU限制失败: {}", e)

    return None


def _collect_metrics_blocking() -> SystemMetricsSnapshot:
    """Collect metrics; blocks ~CPU_SAMPLE_INTERVAL_SECONDS for CPU sampling."""
    process = psutil.Process()
    process.cpu_percent()
    psutil.cpu_percent()
    time.sleep(CPU_SAMPLE_INTERVAL_SECONDS)

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return SystemMetricsSnapshot(
        process_cpu_percent=process.cpu_percent(),
        process_memory_mb=process.memory_info().rss / (1024**2),
        cpu_percent=psutil.cpu_percent(),
        cpu_count=psutil.cpu_count() or 1,
        memory_percent=float(mem.percent),
        memory_used_mb=mem.used / (1024**2),
        memory_total_mb=mem.total / (1024**2),
        disk_percent=float(disk.percent),
        db_size_mb=_get_db_size_mb(),
        log_size_mb=_get_log_dir_size_mb(),
        memory_limit_mb=_get_cgroup_memory_limit_mb(),
        sampled_at=time.monotonic(),
    )


def _instant_metrics() -> SystemMetricsSnapshot:
    """Non-blocking fallback before the first background sample completes."""
    process = psutil.Process()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return SystemMetricsSnapshot(
        process_cpu_percent=process.cpu_percent(),
        process_memory_mb=process.memory_info().rss / (1024**2),
        cpu_percent=psutil.cpu_percent(),
        cpu_count=psutil.cpu_count() or 1,
        memory_percent=float(mem.percent),
        memory_used_mb=mem.used / (1024**2),
        memory_total_mb=mem.total / (1024**2),
        disk_percent=float(disk.percent),
        db_size_mb=0.0,
        log_size_mb=0.0,
        memory_limit_mb=None,
        sampled_at=time.monotonic(),
    )


def build_system_metrics_payload() -> dict[str, Any]:
    snap = _cache if _cache is not None else _instant_metrics()
    return {
        "process_cpu_percent": snap.process_cpu_percent,
        "process_memory_mb": snap.process_memory_mb,
        "db_size_mb": snap.db_size_mb,
        "log_size_mb": snap.log_size_mb,
        "cpu_percent": snap.cpu_percent,
        "cpu_count": snap.cpu_count,
        "memory_percent": snap.memory_percent,
        "memory_used_mb": snap.memory_used_mb,
        "memory_total_mb": snap.memory_total_mb,
        "memory_limit_mb": snap.memory_limit_mb,
        "disk_percent": snap.disk_percent,
    }


async def _sampler_loop() -> None:
    global _cache
    while True:
        try:
            _cache = await asyncio.to_thread(_collect_metrics_blocking)
        except Exception:
            logger.opt(exception=True).warning("系统指标采样失败")
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)


def start_system_metrics_sampler() -> None:
    global _sampler_task
    if _sampler_task is not None:
        return
    _sampler_task = spawn_background_task("系统指标采样", _sampler_loop())


async def stop_system_metrics_sampler() -> None:
    global _sampler_task
    if _sampler_task is None:
        return
    _sampler_task.cancel()
    try:
        await _sampler_task
    except asyncio.CancelledError:
        pass
    _sampler_task = None
