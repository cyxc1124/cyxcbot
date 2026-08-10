"""Settings API schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from shared.config.message_templates import (
    DOUYIN_LINK_TEMPLATE_KEYS,
    DYNAMIC_TEMPLATE_KEYS,
    LINK_TEMPLATE_KEYS,
    LIVE_TEMPLATE_KEYS,
    X_TEMPLATE_KEYS,
)


class CookieStatusResponse(BaseModel):
    configured: bool
    preview: Optional[str] = None


class XProxySettingsResponse(BaseModel):
    enabled: bool = False
    scheme: str = "http"
    host: str = ""
    port: int = 7890
    username: str = ""
    password_configured: bool = False


class CommandAliasEntryModel(BaseModel):
    enabled: bool = True
    triggers: list[str] = Field(default_factory=list)


class SettingsResponse(BaseModel):
    dynamic_monitor_interval: int
    dynamic_monitor_use_stagger: bool = True
    dynamic_enable_screenshot: bool
    dynamic_template_push: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_push"]
    )
    dynamic_template_pinned: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_pinned"]
    )
    dynamic_template_query_latest: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_latest"]
    )
    dynamic_template_query_pinned: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_pinned"]
    )
    dynamic_template_extract: str = Field(
        default=DYNAMIC_TEMPLATE_KEYS["dynamic_template_extract"]
    )
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
    link_template_douyin: str = Field(
        default=DOUYIN_LINK_TEMPLATE_KEYS["link_template_douyin"]
    )
    x_monitor_interval: int = 120
    x_monitor_use_stagger: bool = True
    x_template_push: str = Field(default=X_TEMPLATE_KEYS["x_template_push"])
    bilibili_cookie: CookieStatusResponse
    douyin_cookie: CookieStatusResponse
    x_api_bearer: CookieStatusResponse
    x_proxy: XProxySettingsResponse
    status_check_allowed_qq: list[str] = Field(default_factory=list)
    nonebot_superusers: list[str] = Field(default_factory=list)
    command_aliases: dict[str, CommandAliasEntryModel] = Field(default_factory=dict)
    command_extra_prefixes: list[str] = Field(default_factory=list)
    command_prefixes: list[str] = Field(default_factory=list)
    link_parser_shared_media_dir: str = ""
    link_parser_shared_media_dir_default: str = ""
    link_parser_shared_media_dir_resolved: str = ""


class CookieTestResultResponse(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    username: Optional[str] = None
    uid: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    dynamic_monitor_interval: Optional[int] = Field(default=None, ge=10, le=3600)
    dynamic_monitor_use_stagger: Optional[bool] = None
    dynamic_enable_screenshot: Optional[bool] = None
    dynamic_template_push: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_pinned: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_query_latest: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_query_pinned: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract_empty: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract_failed: Optional[str] = Field(default=None, max_length=500)
    dynamic_template_extract_image_label: Optional[str] = Field(
        default=None, max_length=500
    )
    live_monitor_interval: Optional[int] = Field(default=None, ge=30, le=3600)
    live_monitor_include_info: Optional[bool] = None
    live_monitor_use_websocket: Optional[bool] = None
    live_template_start: Optional[str] = Field(default=None, max_length=500)
    live_template_end: Optional[str] = Field(default=None, max_length=500)
    link_template_video: Optional[str] = Field(default=None, max_length=500)
    link_template_live: Optional[str] = Field(default=None, max_length=500)
    link_template_douyin: Optional[str] = Field(default=None, max_length=500)
    x_monitor_interval: Optional[int] = Field(default=None, ge=10, le=3600)
    x_monitor_use_stagger: Optional[bool] = None
    x_template_push: Optional[str] = Field(default=None, max_length=500)
    x_api_bearer: Optional[str] = None
    x_proxy_enabled: Optional[bool] = None
    x_proxy_scheme: Optional[str] = Field(default=None, max_length=16)
    x_proxy_host: Optional[str] = Field(default=None, max_length=255)
    x_proxy_port: Optional[int] = Field(default=None, ge=1, le=65535)
    x_proxy_username: Optional[str] = Field(default=None, max_length=128)
    x_proxy_password: Optional[str] = None
    status_check_allowed_qq: Optional[list[str]] = None
    nonebot_superusers: Optional[list[str]] = None
    command_aliases: Optional[dict[str, CommandAliasEntryModel]] = None
    command_extra_prefixes: Optional[list[str]] = None
    link_parser_shared_media_dir: Optional[str] = Field(default=None, max_length=512)
