"""
B站直播监控插件配置（从 ConfigService 加载）
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from shared.config.message_templates import LiveMessageTemplates


class Config(BaseModel):
    """B站直播监控插件配置"""

    live_monitor_mapping: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="房间号-群组ID映射配置"
    )

    live_monitor_user_mapping: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="房间号-好友QQ号映射配置"
    )

    live_at_all: Dict[str, bool] = Field(
        default_factory=dict,
        description="房间号-是否@全体成员"
    )

    monitor_interval: int = Field(
        default=60,
        description="直播状态检查间隔（秒）"
    )

    include_room_info: bool = Field(
        default=True,
        description="是否在通知中包含房间详细信息"
    )

    bilibili_cookie: Optional[str] = Field(
        default=None,
        description="B站用户Cookie（可选）"
    )

    use_websocket: bool = Field(
        default=True,
        description="是否启用 WebSocket 实时监控"
    )

    message_templates: LiveMessageTemplates = Field(
        default_factory=LiveMessageTemplates,
        description="直播推送消息模板"
    )

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            live_monitor_mapping=snap.live_monitor_mapping,
            live_monitor_user_mapping=snap.live_monitor_user_mapping,
            live_at_all=snap.live_at_all,
            monitor_interval=snap.live_monitor_interval,
            include_room_info=snap.live_monitor_include_info,
            bilibili_cookie=snap.bilibili_cookie or None,
            use_websocket=snap.live_monitor_use_websocket,
            message_templates=snap.live_message_templates,
        )
