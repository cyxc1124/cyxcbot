from typing import Dict, List

from pydantic import BaseModel, Field

from shared.config.message_templates import XMessageTemplates
from shared.config.proxy import ProxyConfig


class Config(BaseModel):
    """X (Twitter) 监控插件配置（从 ConfigService 加载）"""

    x_monitor_mapping: Dict[str, List[str]] = Field(
        default_factory=dict, description="X 用户名-群组ID映射配置"
    )

    x_monitor_user_mapping: Dict[str, List[str]] = Field(
        default_factory=dict, description="X 用户名-好友QQ号映射配置"
    )

    x_at_all: Dict[str, bool] = Field(
        default_factory=dict, description="X 用户名-是否@全体成员"
    )

    monitor_interval: int = Field(default=120, description="监控间隔时间（秒）")

    use_stagger_poll: bool = Field(
        default=True, description="是否启用分散检查（关闭则为批量检查）"
    )

    message_templates: XMessageTemplates = Field(
        default_factory=XMessageTemplates, description="X 推送消息模板"
    )

    x_api_bearer: str = Field(default="", description="X API Bearer Token")

    x_proxy: ProxyConfig = Field(
        default_factory=ProxyConfig, description="X API 出站代理"
    )

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            x_monitor_mapping=snap.x_monitor_mapping,
            x_monitor_user_mapping=snap.x_monitor_user_mapping,
            x_at_all=snap.x_at_all,
            monitor_interval=snap.x_monitor_interval,
            use_stagger_poll=snap.x_monitor_use_stagger,
            message_templates=snap.x_message_templates,
            x_api_bearer=snap.x_api_bearer,
            x_proxy=snap.x_proxy,
        )
