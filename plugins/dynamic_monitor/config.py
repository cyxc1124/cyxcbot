from pydantic import BaseModel, Field
from typing import List, Dict


class Config(BaseModel):
    """UP主动态监控插件配置（从 ConfigService 加载）"""

    dynamic_monitor_mapping: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="UP主UID-群组ID映射配置"
    )

    monitor_interval: int = Field(
        default=30,
        description="监控间隔时间（秒）"
    )

    enable_screenshot: bool = Field(
        default=True,
        description="是否在推送消息中包含动态网页截图"
    )

    bilibili_cookie: str = Field(
        default="",
        description="B站用户Cookie，用于提高API请求成功率"
    )

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            dynamic_monitor_mapping=snap.dynamic_monitor_mapping,
            monitor_interval=snap.dynamic_monitor_interval,
            enable_screenshot=snap.dynamic_enable_screenshot,
            bilibili_cookie=snap.bilibili_cookie,
        )

    def get_uids_by_group_id(self, group_id: str) -> List[str]:
        """根据群组ID反向查找对应的UP主UID列表"""
        uids = []
        for uid, group_ids in self.dynamic_monitor_mapping.items():
            if group_id in group_ids:
                uids.append(uid)
        return uids
