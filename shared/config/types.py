"""Dataclass snapshots for hot-reloadable configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AppConfigSnapshot:
    """Full application configuration snapshot loaded from DB."""

    dynamic_monitor_mapping: Dict[str, List[str]] = field(default_factory=dict)
    dynamic_at_all: Dict[str, bool] = field(default_factory=dict)
    dynamic_monitor_interval: int = 30
    dynamic_enable_screenshot: bool = True
    live_monitor_mapping: Dict[str, List[str]] = field(default_factory=dict)
    live_at_all: Dict[str, bool] = field(default_factory=dict)
    live_monitor_interval: int = 60
    live_monitor_include_info: bool = True
    live_monitor_use_websocket: bool = True
    bilibili_cookie: str = ""
    bilibili_cookie_set: bool = False
    audit_log_retention_days: int = 90
    event_retention_days: int = 90
    message_group_restrict: bool = False
    message_enabled_group_ids: List[str] = field(default_factory=list)
