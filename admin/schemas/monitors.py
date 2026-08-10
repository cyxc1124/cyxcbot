"""Monitor status API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MonitorPollSchedule(BaseModel):
    strategy: str
    target_count: int
    configured_interval_seconds: int
    min_tick_interval_seconds: Optional[float] = None
    poll_interval_seconds: Optional[int] = None
    batch_gap_seconds: Optional[float] = None
    use_websocket: Optional[bool] = None
    tick_interval_seconds: float
    per_target_cycle_seconds: float
    requests_per_second_avg: float
    requests_per_second_peak: float
    meets_configured_interval: bool
    warning: Optional[str] = None


class MonitorStatusResponse(BaseModel):
    running: bool
    uptime_seconds: int
    dynamic_running: bool
    live_running: bool
    x_running: bool = False
    dynamic_target_count: int
    live_target_count: int
    x_target_count: int = 0


class DynamicMonitorDetail(BaseModel):
    uid: str
    last_dynamic_id: int
    initialized: bool
    pinned_dynamic_id: Optional[int]
    group_count: int


class LiveMonitorDetail(BaseModel):
    room_id: str
    previous_status: Optional[str]
    streamer_name: Optional[str]
    is_living: Optional[bool]
    group_count: int


class XMonitorDetail(BaseModel):
    username: str
    last_tweet_id: str
    initialized: bool
    group_count: int


class DynamicMonitorStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    target_count: int
    poll_schedule: MonitorPollSchedule
    last_check_at: Optional[str] = None
    last_fetch_at: Optional[str] = None
    last_error: Optional[str] = None
    checks_total: int = 0
    new_dynamics_total: int = 0
    targets: List[DynamicMonitorDetail] = []


class LiveMonitorStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    use_websocket: bool
    target_count: int
    poll_schedule: MonitorPollSchedule
    last_check_at: Optional[str] = None
    last_error: Optional[str] = None
    live_rooms: int = 0
    checks_total: int = 0
    targets: List[LiveMonitorDetail] = []


class XMonitorStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    target_count: int
    poll_schedule: MonitorPollSchedule
    last_check_at: Optional[str] = None
    last_error: Optional[str] = None
    checks_total: int = 0
    new_tweets_total: int = 0
    targets: List[XMonitorDetail] = []


class ManualCheckResponse(BaseModel):
    success: bool
    message: str
    result: Optional[Dict[str, Any]] = None


class SystemMonitorStatusResponse(BaseModel):
    process_cpu_percent: float
    process_memory_mb: float
    db_size_mb: float
    log_size_mb: float
    cpu_percent: float
    cpu_count: int
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    memory_limit_mb: Optional[float] = None
    disk_percent: float
