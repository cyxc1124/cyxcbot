"""Settings API schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CookieStatusResponse(BaseModel):
    configured: bool
    preview: Optional[str] = None


class SettingsResponse(BaseModel):
    dynamic_monitor_interval: int
    dynamic_enable_screenshot: bool
    live_monitor_interval: int
    live_monitor_include_info: bool
    live_monitor_use_websocket: bool
    bilibili_cookie: CookieStatusResponse
    audit_log_retention_days: int
    event_retention_days: int


class CookieTestResultResponse(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    username: Optional[str] = None
    uid: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    dynamic_monitor_interval: Optional[int] = Field(default=None, ge=10, le=3600)
    dynamic_enable_screenshot: Optional[bool] = None
    live_monitor_interval: Optional[int] = Field(default=None, ge=30, le=3600)
    live_monitor_include_info: Optional[bool] = None
    live_monitor_use_websocket: Optional[bool] = None
    audit_log_retention_days: Optional[int] = Field(default=None, ge=0, le=3650)
    event_retention_days: Optional[int] = Field(default=None, ge=0, le=3650)
