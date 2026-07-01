"""Prometheus exposition metrics for cyxcbot."""

from __future__ import annotations

from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    generate_latest,
)

REGISTRY = CollectorRegistry()

PROCESS_CPU_PERCENT = Gauge(
    "cyxcbot_process_cpu_percent",
    "CPU usage of the bot process (percent)",
    registry=REGISTRY,
)
PROCESS_RESIDENT_MEMORY_BYTES = Gauge(
    "cyxcbot_process_resident_memory_bytes",
    "Resident memory of the bot process (bytes)",
    registry=REGISTRY,
)
SYSTEM_CPU_PERCENT = Gauge(
    "cyxcbot_system_cpu_percent",
    "System-wide CPU usage (percent)",
    registry=REGISTRY,
)
SYSTEM_MEMORY_BYTES = Gauge(
    "cyxcbot_system_memory_bytes",
    "System memory used (bytes)",
    registry=REGISTRY,
)
SYSTEM_MEMORY_TOTAL_BYTES = Gauge(
    "cyxcbot_system_memory_total_bytes",
    "System memory total (bytes)",
    registry=REGISTRY,
)
SYSTEM_DISK_USED_PERCENT = Gauge(
    "cyxcbot_system_disk_used_percent",
    "Root filesystem used (percent)",
    registry=REGISTRY,
)
PROCESS_MEMORY_LIMIT_BYTES = Gauge(
    "cyxcbot_process_memory_limit_bytes",
    "Cgroup memory limit for the bot process (bytes); omitted when unlimited",
    registry=REGISTRY,
)
DATABASE_SIZE_BYTES = Gauge(
    "cyxcbot_database_size_bytes",
    "SQLite database file size (bytes)",
    registry=REGISTRY,
)
LOG_DIRECTORY_SIZE_BYTES = Gauge(
    "cyxcbot_log_directory_size_bytes",
    "Total size of log directory files (bytes)",
    registry=REGISTRY,
)
UPTIME_SECONDS = Gauge(
    "cyxcbot_uptime_seconds",
    "Bot process uptime (seconds)",
    registry=REGISTRY,
)
DYNAMIC_MONITOR_ENABLED = Gauge(
    "cyxcbot_dynamic_monitor_enabled",
    "Whether dynamic monitor is running (1=yes, 0=no)",
    registry=REGISTRY,
)
LIVE_MONITOR_ENABLED = Gauge(
    "cyxcbot_live_monitor_enabled",
    "Whether live monitor is running (1=yes, 0=no)",
    registry=REGISTRY,
)
DYNAMIC_MONITOR_TARGETS = Gauge(
    "cyxcbot_dynamic_monitor_targets",
    "Number of configured dynamic monitor targets",
    registry=REGISTRY,
)
LIVE_MONITOR_TARGETS = Gauge(
    "cyxcbot_live_monitor_targets",
    "Number of configured live monitor targets",
    registry=REGISTRY,
)
DYNAMIC_MONITOR_CHECKS_TOTAL = Gauge(
    "cyxcbot_dynamic_monitor_checks_total",
    "Total dynamic monitor target checks since process start",
    registry=REGISTRY,
)
LIVE_MONITOR_CHECKS_TOTAL = Gauge(
    "cyxcbot_live_monitor_checks_total",
    "Total live monitor room checks since process start",
    registry=REGISTRY,
)
DYNAMIC_MONITOR_NEW_DYNAMICS_TOTAL = Gauge(
    "cyxcbot_dynamic_monitor_new_dynamics_total",
    "Total new dynamics detected since process start",
    registry=REGISTRY,
)


def apply_system_metrics(payload: dict[str, Any]) -> None:
    PROCESS_CPU_PERCENT.set(payload["process_cpu_percent"])
    PROCESS_RESIDENT_MEMORY_BYTES.set(payload["process_memory_mb"] * 1024 * 1024)
    SYSTEM_CPU_PERCENT.set(payload["cpu_percent"])
    SYSTEM_MEMORY_BYTES.set(payload["memory_used_mb"] * 1024 * 1024)
    SYSTEM_MEMORY_TOTAL_BYTES.set(payload["memory_total_mb"] * 1024 * 1024)
    SYSTEM_DISK_USED_PERCENT.set(payload["disk_percent"])
    DATABASE_SIZE_BYTES.set(payload["db_size_mb"] * 1024 * 1024)
    LOG_DIRECTORY_SIZE_BYTES.set(payload["log_size_mb"] * 1024 * 1024)

    limit_mb = payload.get("memory_limit_mb")
    if limit_mb is not None:
        PROCESS_MEMORY_LIMIT_BYTES.set(limit_mb * 1024 * 1024)
    else:
        PROCESS_MEMORY_LIMIT_BYTES.set(0)


def apply_monitor_metrics(monitor: dict[str, Any]) -> None:
    DYNAMIC_MONITOR_ENABLED.set(1 if monitor.get("dynamic_running") else 0)
    LIVE_MONITOR_ENABLED.set(1 if monitor.get("live_running") else 0)
    DYNAMIC_MONITOR_TARGETS.set(monitor.get("dynamic_target_count", 0))
    LIVE_MONITOR_TARGETS.set(monitor.get("live_target_count", 0))
    DYNAMIC_MONITOR_CHECKS_TOTAL.set(monitor.get("dynamic_checks_total", 0))
    LIVE_MONITOR_CHECKS_TOTAL.set(monitor.get("live_checks_total", 0))
    DYNAMIC_MONITOR_NEW_DYNAMICS_TOTAL.set(monitor.get("dynamic_new_dynamics_total", 0))


def refresh_prometheus_metrics() -> None:
    from admin.services.monitor_bridge import (
        get_monitor_status,
        get_system_monitor_status,
    )
    from shared.runtime import get_uptime_seconds

    apply_system_metrics(get_system_monitor_status())
    apply_monitor_metrics(get_monitor_status())
    UPTIME_SECONDS.set(get_uptime_seconds())


def render_prometheus_metrics() -> tuple[bytes, str]:
    refresh_prometheus_metrics()
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
