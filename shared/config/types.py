"""Dataclass snapshots for hot-reloadable configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from shared.config.link_parser_policy import (
    LinkParserGroupPolicyRecord,
    LinkParserUserPolicyRecord,
)
from shared.config.message_templates import (
    DynamicMessageTemplates,
    LinkMessageTemplates,
    LiveMessageTemplates,
    dynamic_templates_from_settings,
    link_templates_from_settings,
    live_templates_from_settings,
)


@dataclass
class AppConfigSnapshot:
    """Full application configuration snapshot loaded from DB."""

    dynamic_monitor_mapping: Dict[str, List[str]] = field(default_factory=dict)
    dynamic_monitor_user_mapping: Dict[str, List[str]] = field(default_factory=dict)
    dynamic_at_all: Dict[str, bool] = field(default_factory=dict)
    dynamic_monitor_interval: int = 30
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
    live_message_templates: LiveMessageTemplates = field(default_factory=LiveMessageTemplates)
    link_message_templates: LinkMessageTemplates = field(default_factory=LinkMessageTemplates)
    bilibili_cookie: str = ""
    bilibili_cookie_set: bool = False
    audit_log_retention_days: int = 90
    event_retention_days: int = 90
    message_group_restrict: bool = True
    message_enabled_group_ids: List[str] = field(default_factory=list)
    message_private_restrict: bool = True
    message_enabled_user_ids: List[str] = field(default_factory=list)
    status_check_allowed_qq: List[str] = field(default_factory=list)
    nonebot_superusers: List[str] = field(default_factory=list)
    bilibili_link_parser_enabled: bool = False
    bilibili_link_parser_private_enabled: bool = False
    bilibili_link_parser_video_enabled: bool = False
    bilibili_link_parser_live_enabled: bool = False
    link_parser_group_policies: Dict[str, LinkParserGroupPolicyRecord] = field(
        default_factory=dict
    )
    link_parser_user_policies: Dict[str, LinkParserUserPolicyRecord] = field(
        default_factory=dict
    )
