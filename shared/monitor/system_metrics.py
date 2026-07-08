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

# cgroup v1/v2 根路径。未做 cgroup namespace 隔离的宿主机上，这不一定是
# 本进程自己的限制——具体见 _own_cgroup_memory_limit_candidates()。
_CGROUP_MEMORY_LIMIT_PATTERNS = [
    "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    "/sys/fs/cgroup/memory.max",
]
# 内存限制文件名 -> 同目录下用量文件名（cgroup v1/v2 用量与限制始终同目录）
_CGROUP_MEMORY_USAGE_FILENAMES = {
    "memory.limit_in_bytes": "memory.usage_in_bytes",
    "memory.max": "memory.current",
}
# 64 位内核 cgroup v1 "无限制"哨兵值：LLONG_MAX（2^63-1）按 4096 字节页对齐
# 后的结果，约 8388608 TiB。真实场景可能显式配置 1 TiB 甚至更大的限制，
# 因此阈值必须紧贴内核哨兵值本身，不能用 1 TiB 这类"看起来很大"的整数——
# 否则会把合法的大内存限制误判为未设置。
_CGROUP_UNLIMITED_THRESHOLD_BYTES = 9223372036854771712

_DOCKERENV_PATH = "/.dockerenv"
_PROC_1_CGROUP_PATH = "/proc/1/cgroup"
_PROC_SELF_CGROUP_PATH = "/proc/self/cgroup"
_CGROUP_V1_MEMORY_ROOT = "/sys/fs/cgroup/memory"
_CGROUP_UNIFIED_ROOT = "/sys/fs/cgroup"
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
    paths: list[str], *, skip_if_ge: int | None = None
) -> tuple[int | None, str | None]:
    """按候选路径顺序查找第一个有效的 cgroup 数值文件，返回 (数值, 命中路径)。

    根路径（如 `/sys/fs/cgroup/memory/memory.limit_in_bytes`）在未做 cgroup
    namespace 隔离的环境下几乎总是存在，其"无限制"哨兵值是一个巨大的合法数字，
    并非 `max` 字符串。若 `skip_if_ge` 给定，命中值达到该阈值时视为"此路径未设置"，
    跳过并继续尝试后续路径，而不是直接返回。
    """
    for path in paths:
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


def _own_cgroup_subpath(controller: str) -> str | None:
    """读取 /proc/self/cgroup，返回本进程在指定 controller 下的相对 cgroup 路径。

    cgroup v2 统一层级行的 controllers 字段为空，适用于所有 controller。
    读取失败、未找到匹配行、或本进程就在根路径（通常意味着已启用 cgroup
    namespace 隔离，`/sys/fs/cgroup/...` 本身即本进程的 cgroup）时返回 None，
    交由调用方退化为根路径直读。
    """
    try:
        lines = Path(_PROC_SELF_CGROUP_PATH).read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        _, _, rest = line.partition(":")
        controllers, _, subpath = rest.partition(":")
        if controllers == "" or controller in controllers.split(","):
            subpath = subpath.strip("/")
            return subpath or None
    return None


def _own_cgroup_memory_limit_candidates() -> list[str]:
    """本进程专属的内存限制候选路径，按优先级排序。

    未做 cgroup namespace 隔离的宿主机上，`/sys/fs/cgroup/memory/kubepods.slice/`
    等目录下会并列存在同机其他 Pod/容器的 cgroup，用通配符盲目搜索可能读到
    别的工作负载的限制/用量。这里优先用 /proc/self/cgroup 推导出本进程精确的
    cgroup 子路径；推导失败时才退化为根路径（此时根路径本身就是本进程的）。
    """
    subpath = _own_cgroup_subpath("memory")
    candidates: list[str] = []
    if subpath:
        candidates.append(f"{_CGROUP_V1_MEMORY_ROOT}/{subpath}/memory.limit_in_bytes")
        candidates.append(f"{_CGROUP_UNIFIED_ROOT}/{subpath}/memory.max")
    candidates.extend(_CGROUP_MEMORY_LIMIT_PATTERNS)
    return candidates


def _get_cgroup_memory_limit_mb() -> float | None:
    limit_bytes, _ = _find_cgroup_value(
        _own_cgroup_memory_limit_candidates(),
        skip_if_ge=_CGROUP_UNLIMITED_THRESHOLD_BYTES,
    )
    if limit_bytes is None:
        return None
    return limit_bytes / (1024**2)


def _sibling_cgroup_usage_path(limit_file: str) -> str | None:
    """按命中的限制文件名，推导同一 cgroup 目录下对应的用量文件路径。

    用量必须与限制来自同一 cgroup 目录，否则会把宿主机/根 cgroup 的整体用量
    和某个容器 slice 的限制值错误配对，算出 >100% 用量或负数可用内存。
    """
    path = Path(limit_file)
    usage_name = _CGROUP_MEMORY_USAGE_FILENAMES.get(path.name)
    return str(path.with_name(usage_name)) if usage_name else None


def get_container_memory_info() -> dict[str, Any] | None:
    """获取容器内存信息（cgroup 限制 + 同目录用量），用于 `/status` 等展示场景。"""
    try:
        limit_bytes, limit_file = _find_cgroup_value(
            _own_cgroup_memory_limit_candidates(),
            skip_if_ge=_CGROUP_UNLIMITED_THRESHOLD_BYTES,
        )
        if limit_bytes is None or limit_file is None:
            logger.debug("未找到有效的容器内存限制")
            return None

        usage_path = _sibling_cgroup_usage_path(limit_file)
        usage_bytes, usage_file = (
            _find_cgroup_value([usage_path]) if usage_path else (None, None)
        )

        if usage_bytes is None:
            logger.debug("内存限制 {} 所在目录未找到匹配的用量文件", limit_file)
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
