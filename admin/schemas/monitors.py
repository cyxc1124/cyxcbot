"""Monitor status API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MonitorStatusResponse(BaseModel):
    dynamic_running: bool
    live_running: bool
    dynamic_target_count: int
    live_target_count: int


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


class DynamicMonitorStatusResponse(BaseModel):
    running: bool
    interval: int
    targets: List[DynamicMonitorDetail]


class LiveMonitorStatusResponse(BaseModel):
    running: bool
    interval: int
    use_websocket: bool
    targets: List[LiveMonitorDetail]


class ManualCheckResponse(BaseModel):
    success: bool
    message: str
    result: Optional[Dict[str, Any]] = None


class SystemMonitorStatusResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    python_version: str
    bot_version: str
