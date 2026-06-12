from typing import Dict, List

from pydantic import BaseModel, Field

from shared.config.message_templates import DynamicMessageTemplates


class Config(BaseModel):
    """UP主动态监控插件配置（从 ConfigService 加载）"""

    dynamic_monitor_mapping: Dict[str, List[str]] = Field(
        default_factory=dict, description="UP主UID-群组ID映射配置"
    )

    dynamic_monitor_user_mapping: Dict[str, List[str]] = Field(
        default_factory=dict, description="UP主UID-好友QQ号映射配置"
    )

    dynamic_at_all: Dict[str, bool] = Field(
        default_factory=dict, description="UP主UID-是否@全体成员"
    )

    monitor_interval: int = Field(default=30, description="监控间隔时间（秒）")

    use_stagger_poll: bool = Field(
        default=True, description="是否启用分散检查（关闭则为批量检查）"
    )

    enable_screenshot: bool = Field(
        default=True, description="是否在推送消息中包含动态网页截图"
    )

    message_templates: DynamicMessageTemplates = Field(
        default_factory=DynamicMessageTemplates, description="动态推送消息模板"
    )

    bilibili_cookie: str = Field(
        default="", description="B站用户Cookie，用于提高API请求成功率"
    )

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            dynamic_monitor_mapping=snap.dynamic_monitor_mapping,
            dynamic_monitor_user_mapping=snap.dynamic_monitor_user_mapping,
            dynamic_at_all=snap.dynamic_at_all,
            monitor_interval=snap.dynamic_monitor_interval,
            use_stagger_poll=snap.dynamic_monitor_use_stagger,
            enable_screenshot=snap.dynamic_enable_screenshot,
            message_templates=snap.dynamic_message_templates,
            bilibili_cookie=snap.bilibili_cookie,
        )

    def get_uids_by_group_id(self, group_id: str) -> List[str]:
        """根据群组ID反向查找对应的UP主UID列表"""
        uids = []
        for uid, group_ids in self.dynamic_monitor_mapping.items():
            if group_id in group_ids:
                uids.append(uid)
        return uids
