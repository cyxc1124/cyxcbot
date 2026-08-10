"""Dataclass snapshots for hot-reloadable configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from shared.config.command_aliases import DEFAULT_EXTRA_PREFIXES, CommandAliasEntry
from shared.config.douyin_link_parser_policy import (
    DouyinLinkParserGroupPolicyRecord,
    DouyinLinkParserUserPolicyRecord,
)
from shared.config.link_parser_policy import (
    LinkParserGroupPolicyRecord,
    LinkParserUserPolicyRecord,
)
from shared.config.message_templates import (
    DouyinLinkMessageTemplates,
    DynamicMessageTemplates,
    LinkMessageTemplates,
    LiveMessageTemplates,
    XMessageTemplates,
)
from shared.config.proxy import ProxyConfig
from shared.config.rust_rcon import RustRconBindingRecord
from shared.config.rust_rcon_custom import RustRconCustomCommandRecord
from shared.config.rust_rcon_policy import (
    RustRconGroupPolicyRecord,
    RustRconUserPolicyRecord,
)


@dataclass
class AppConfigSnapshot:
    """Full application configuration snapshot loaded from DB."""

    dynamic_monitor_mapping: Dict[str, List[str]] = field(default_factory=dict)
    dynamic_monitor_user_mapping: Dict[str, List[str]] = field(default_factory=dict)
    dynamic_subscription_mapping: Dict[str, List[str]] = field(default_factory=dict)
    dynamic_subscription_user_mapping: Dict[str, List[str]] = field(
        default_factory=dict
    )
    dynamic_at_all: Dict[str, bool] = field(default_factory=dict)
    dynamic_monitor_interval: int = 30
    dynamic_monitor_use_stagger: bool = True
    dynamic_enable_screenshot: bool = True
    dynamic_message_templates: DynamicMessageTemplates = field(
        default_factory=DynamicMessageTemplates
    )
    live_monitor_mapping: Dict[str, List[str]] = field(default_factory=dict)
    live_monitor_user_mapping: Dict[str, List[str]] = field(default_factory=dict)
    live_at_all: Dict[str, bool] = field(default_factory=dict)
    live_monitor_interval: int = 60
    live_monitor_include_info: bool = True
    live_monitor_use_websocket: bool = True
    live_message_templates: LiveMessageTemplates = field(
        default_factory=LiveMessageTemplates
    )
    link_message_templates: LinkMessageTemplates = field(
        default_factory=LinkMessageTemplates
    )
    douyin_link_message_templates: DouyinLinkMessageTemplates = field(
        default_factory=DouyinLinkMessageTemplates
    )
    bilibili_cookie: str = ""
    bilibili_cookie_set: bool = False
    douyin_cookie: str = ""
    douyin_cookie_set: bool = False
    message_group_restrict: bool = True
    message_enabled_group_ids: List[str] = field(default_factory=list)
    message_private_restrict: bool = True
    message_enabled_user_ids: List[str] = field(default_factory=list)
    status_check_group_restrict: bool = True
    status_check_enabled_group_ids: List[str] = field(default_factory=list)
    status_check_private_restrict: bool = True
    status_check_enabled_user_ids: List[str] = field(default_factory=list)
    status_check_show_detailed: bool = True
    status_check_show_uptime: bool = True
    status_check_show_memory: bool = True
    status_check_allowed_qq: List[str] = field(default_factory=list)
    group_special_title_restrict: bool = True
    group_special_title_enabled_group_ids: List[str] = field(default_factory=list)
    group_special_title_daily_limit: int = 10
    nonebot_superusers: List[str] = field(default_factory=list)
    link_parser_group_policies: Dict[str, LinkParserGroupPolicyRecord] = field(
        default_factory=dict
    )
    link_parser_user_policies: Dict[str, LinkParserUserPolicyRecord] = field(
        default_factory=dict
    )
    douyin_link_parser_group_policies: Dict[str, DouyinLinkParserGroupPolicyRecord] = (
        field(default_factory=dict)
    )
    douyin_link_parser_user_policies: Dict[str, DouyinLinkParserUserPolicyRecord] = (
        field(default_factory=dict)
    )
    command_aliases: Dict[str, CommandAliasEntry] = field(default_factory=dict)
    command_extra_prefixes: List[str] = field(
        default_factory=lambda: list(DEFAULT_EXTRA_PREFIXES)
    )
    rust_rcon_bindings: List[RustRconBindingRecord] = field(default_factory=list)
    rust_rcon_custom_commands: List[RustRconCustomCommandRecord] = field(
        default_factory=list
    )
    rust_rcon_group_policies: Dict[str, RustRconGroupPolicyRecord] = field(
        default_factory=dict
    )
    rust_rcon_user_policies: Dict[str, RustRconUserPolicyRecord] = field(
        default_factory=dict
    )
    rust_checkin_points_min: int = 1
    rust_checkin_points_max: int = 10
    rust_checkin_online_bonus_points: int = 50
    rust_steam_bind_bonus_points: int = 200
    rust_checkin_rcon_binding_id: int = 0
    # B 站链接解析发视频：与协议端共享的目录（空=平台默认）
    link_parser_shared_media_dir: str = ""
    x_monitor_mapping: Dict[str, List[str]] = field(default_factory=dict)
    x_monitor_user_mapping: Dict[str, List[str]] = field(default_factory=dict)
    x_at_all: Dict[str, bool] = field(default_factory=dict)
    # username -> X numeric user id / display name（来自 XTarget，避免轮询重复查用户）
    x_user_ids: Dict[str, str] = field(default_factory=dict)
    x_display_names: Dict[str, str] = field(default_factory=dict)
    x_monitor_interval: int = 120
    x_monitor_use_stagger: bool = True
    x_message_templates: XMessageTemplates = field(default_factory=XMessageTemplates)
    x_api_bearer: str = ""
    x_api_bearer_set: bool = False
    x_proxy: ProxyConfig = field(default_factory=ProxyConfig)
