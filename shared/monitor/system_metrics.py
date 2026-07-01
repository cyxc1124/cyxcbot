"""Background system metrics sampler with in-memory cache (issue #92)."""

from __future__ import annotations

import asyncio
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


def _get_cgroup_memory_limit_mb() -> float | None:
    try:
        raw = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if raw != "max":
            return int(raw) / (1024**2)
    except OSError, ValueError:
        pass

    try:
        raw = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes").read_text().strip()
        limit_bytes = int(raw)
        if limit_bytes > 0 and limit_bytes < 2**60:
            return limit_bytes / (1024**2)
    except OSError, ValueError:
        pass

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
