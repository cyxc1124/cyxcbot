"""Settings API schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from shared.config.message_templates import DYNAMIC_TEMPLATE_KEYS, LINK_TEMPLATE_KEYS, LIVE_TEMPLATE_KEYS


class CookieStatusResponse(BaseModel):
    configured: bool
    preview: Optional[str] = None


class SettingsResponse(BaseModel):
    dynamic_monitor_interval: int
    dynamic_enable_screenshot: bool
    dynamic_template_push: str = Field(default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_push"])
    dynamic_template_pinned: str = Field(default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_pinned"])
    dynamic_template_query_latest: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_latest"]
    )
    dynamic_template_query_pinned: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_pinned"]
    )
    dynamic_template_extract: str = Field(default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_extract"])
    dynamic_template_extract_empty: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_extract_empty"]
    )
    dynamic_template_extract_failed: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_extract_failed"]
    )
    dynamic_template_extract_image_label: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_extract_image_label"]
    )
    live_monitor_interval: int
    live_monitor_include_info: bool
    live_monitor_use_websocket: bool
    live_template_start: str = Field(default=LIVE_TEMPLATE_KEYS["live_template_start"])
    live_template_end: str = Field(default=LIVE_TEMPLATE_KEYS["live_template_end"])
    link_template_video: str = Field(default=LINK_TEMPLATE_KEYS["link_template_video"])
    link_template_live: str = Field(default=LINK_TEMPLATE_KEYS["link_template_live"])
    bilibili_cookie: CookieStatusResponse
    status_check_allowed_qq: list[str] = Field(default_factory=list)
    nonebot_superusers: list[str] = Field(default_factory=list)


class CookieTestResultResponse(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    username: Optional[str] = None
    uid: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    dynamic_monitor_interval: Optional[int] = Field(default=None, ge=10, le=3600)
    dynamic_enable_screenshot: Optional[bool] = None
    dynamic_template_push: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_pinned: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_query_latest: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_query_pinned: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract_empty: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract_failed: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract_image_label: Optional[str] = Field(default=None, max_length=500)
    live_monitor_interval: Optional[int] = Field(default=None, ge=30, le=3600)
    live_monitor_include_info: Optional[bool] = None
    live_monitor_use_websocket: Optional[bool] = None
    live_template_start: Optional[str] = Field(default=None, max_length=500)
    live_template_end: Optional[str] = Field(default=None, max_length=500)
    link_template_video: Optional[str] = Field(default=None, max_length=500)
    link_template_live: Optional[str] = Field(default=None, max_length=500)
    status_check_allowed_qq: Optional[list[str]] = None
    nonebot_superusers: Optional[list[str]] = None
