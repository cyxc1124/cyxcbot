"""Settings API schemas."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from shared.config.ai_image import CACHE_MAX_ENTRIES_DEFAULT, CACHE_MAX_ENTRIES_LIMIT
from shared.config.message_templates import (
    DOUYIN_LINK_TEMPLATE_KEYS,
    DYNAMIC_TEMPLATE_KEYS,
    LINK_TEMPLATE_KEYS,
    LIVE_TEMPLATE_KEYS,
    X_LINK_TEMPLATE_KEYS,
    X_TEMPLATE_KEYS,
)
from shared.logging.levels import LogLevel


class CookieStatusResponse(BaseModel):
    configured: bool
    preview: Optional[str] = None


class OfficialQQSettingsResponse(BaseModel):
    app_id: str = ""
    secret: CookieStatusResponse
    is_sandbox: bool = Field(
        default=False, description="兼容旧客户端，固定为 false；官方 QQ 已统一 API"
    )
    use_websocket: bool = False


class ProxyResponse(BaseModel):
    id: str
    name: str
    scheme: Literal["http", "https", "socks5"]
    host: str
    port: int
    username: str = ""
    password_configured: bool = False


class CommandAliasEntryModel(BaseModel):
    enabled: bool = True
    triggers: list[str] = Field(default_factory=list)


class AiImageVisionProviderResponse(BaseModel):
    id: str
    name: str
    api_type: Literal["openai", "anthropic"]
    base_url: str = ""
    model: str
    enabled: bool = True
    proxy_id: str = ""
    api_key_configured: bool = False


class SettingsResponse(BaseModel):
    log_level: LogLevel = "INFO"
    log_file_level: LogLevel = "INFO"
    dynamic_monitor_interval: int
    dynamic_monitor_use_stagger: bool = True
    dynamic_image_mode: Literal["screenshot", "card"] = "screenshot"
    dynamic_card_color_source: Literal["image", "avatar"] = "avatar"
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
    link_template_x: str = Field(default=X_LINK_TEMPLATE_KEYS["link_template_x"])
    x_monitor_interval: int = 120
    x_monitor_use_stagger: bool = True
    x_template_push: str = Field(default=X_TEMPLATE_KEYS["x_template_push"])
    bilibili_cookie: CookieStatusResponse
    douyin_cookie: CookieStatusResponse
    x_api_bearer: CookieStatusResponse
    ai_image_openai_api_key: CookieStatusResponse = Field(
        default_factory=lambda: CookieStatusResponse(configured=False)
    )
    ai_image_local_c2pa_enabled: bool = True
    ai_image_openai_c2pa_enabled: bool = True
    ai_image_openai_synthid_enabled: bool = True
    ai_image_cache_enabled: bool = True
    ai_image_cache_max_entries: int = CACHE_MAX_ENTRIES_DEFAULT
    ai_image_vision_enabled: bool = True
    ai_image_vision_providers: list[AiImageVisionProviderResponse] = Field(
        default_factory=list
    )
    proxies: list[ProxyResponse] = Field(default_factory=list)
    x_proxy_id: str = ""
    ai_image_openai_proxy_id: str = ""
    official_qq: OfficialQQSettingsResponse = Field(
        default_factory=lambda: OfficialQQSettingsResponse(
            secret=CookieStatusResponse(configured=False)
        )
    )
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
    log_level: Optional[LogLevel] = None
    log_file_level: Optional[LogLevel] = None
    dynamic_monitor_interval: Optional[int] = Field(default=None, ge=10, le=3600)
    dynamic_monitor_use_stagger: Optional[bool] = None
    dynamic_image_mode: Optional[Literal["screenshot", "card"]] = None
    dynamic_card_color_source: Optional[Literal["image", "avatar"]] = None
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
    link_template_x: Optional[str] = Field(default=None, max_length=500)
    x_monitor_interval: Optional[int] = Field(default=None, ge=10, le=3600)
    x_monitor_use_stagger: Optional[bool] = None
    x_template_push: Optional[str] = Field(default=None, max_length=500)
    x_api_bearer: Optional[str] = None
    ai_image_openai_api_key: Optional[str] = Field(
        default=None, max_length=512, repr=False
    )
    ai_image_local_c2pa_enabled: Optional[bool] = None
    ai_image_openai_c2pa_enabled: Optional[bool] = None
    ai_image_openai_synthid_enabled: Optional[bool] = None
    ai_image_cache_enabled: Optional[bool] = None
    ai_image_cache_max_entries: Optional[int] = Field(
        default=None, ge=1, le=CACHE_MAX_ENTRIES_LIMIT
    )
    ai_image_vision_enabled: Optional[bool] = None
    # 选用「系统 → 网络代理」中的代理 id；空字符串表示直接连接。
    x_proxy_id: Optional[str] = Field(default=None, max_length=32)
    ai_image_openai_proxy_id: Optional[str] = Field(default=None, max_length=32)
    status_check_allowed_qq: Optional[list[str]] = None
    nonebot_superusers: Optional[list[str]] = None
    command_aliases: Optional[dict[str, CommandAliasEntryModel]] = None
    command_extra_prefixes: Optional[list[str]] = None
    link_parser_shared_media_dir: Optional[str] = Field(default=None, max_length=512)
    official_qq_app_id: Optional[str] = Field(default=None, max_length=64)
    official_qq_app_secret: Optional[str] = None
    official_qq_is_sandbox: Optional[bool] = Field(
        default=None, description="兼容旧客户端，仅接受 false"
    )
    official_qq_use_websocket: Optional[bool] = None
