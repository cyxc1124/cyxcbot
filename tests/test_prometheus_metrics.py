"""Tests for Prometheus /metrics exposition."""

from __future__ import annotations

import time

import shared.monitor.prometheus_metrics as prometheus_metrics


def _sample_payload() -> dict:
    return {
        "process_cpu_percent": 12.5,
        "process_memory_mb": 128.0,
        "cpu_percent": 40.0,
        "memory_used_mb": 4096.0,
        "memory_total_mb": 8192.0,
        "disk_percent": 55.0,
        "db_size_mb": 2.0,
        "log_size_mb": 10.0,
        "memory_limit_mb": 512.0,
    }


def _sample_monitor() -> dict:
    return {
        "dynamic_running": True,
        "live_running": False,
        "dynamic_target_count": 3,
        "live_target_count": 5,
        "dynamic_checks_total": 120,
        "live_checks_total": 480,
        "dynamic_new_dynamics_total": 7,
    }


def test_apply_system_metrics_exposes_expected_series():
    prometheus_metrics.apply_system_metrics(_sample_payload())
    prometheus_metrics.apply_monitor_metrics(_sample_monitor())
    prometheus_metrics.UPTIME_SECONDS.set(3600)

    body = prometheus_metrics.generate_latest(prometheus_metrics.REGISTRY).decode()

    assert "cyxcbot_process_cpu_percent 12.5" in body
    assert "cyxcbot_process_resident_memory_bytes" in body
    assert "cyxcbot_system_cpu_percent 40.0" in body
    assert "cyxcbot_database_size_bytes" in body
    assert "cyxcbot_dynamic_monitor_enabled 1.0" in body
    assert "cyxcbot_live_monitor_enabled 0.0" in body
    assert "cyxcbot_dynamic_monitor_targets 3.0" in body
    assert "cyxcbot_dynamic_monitor_checks_total 120.0" in body
    assert "cyxcbot_live_monitor_checks_total 480.0" in body
    assert "cyxcbot_dynamic_monitor_new_dynamics_total 7.0" in body
    assert "cyxcbot_uptime_seconds 3600.0" in body


def test_render_prometheus_metrics_returns_prometheus_format(monkeypatch):
    def fake_refresh() -> None:
        prometheus_metrics.apply_system_metrics(_sample_payload())
        prometheus_metrics.apply_monitor_metrics(_sample_monitor())
        prometheus_metrics.UPTIME_SECONDS.set(42)

    monkeypatch.setattr(prometheus_metrics, "refresh_prometheus_metrics", fake_refresh)

    start = time.monotonic()
    body, content_type = prometheus_metrics.render_prometheus_metrics()
    elapsed = time.monotonic() - start

    assert elapsed < 0.05
    assert content_type == prometheus_metrics.CONTENT_TYPE_LATEST
    text = body.decode()
    assert "cyxcbot_process_cpu_percent 12.5" in text
    assert "cyxcbot_uptime_seconds 42.0" in text
