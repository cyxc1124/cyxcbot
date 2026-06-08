"""状态查询插件配置（从 ConfigService 加载）"""

from pydantic import BaseModel, Field


class Config(BaseModel):
    """状态查询插件配置（保留插件配置入口，实际值由 ConfigService 提供）"""

    show_detailed_status: bool = Field(default=True, description="是否显示详细状态信息")
    show_uptime: bool = Field(default=True, description="是否显示机器人运行时间")
    show_memory_usage: bool = Field(default=True, description="是否显示内存使用情况")

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            show_detailed_status=snap.status_check_show_detailed,
            show_uptime=snap.status_check_show_uptime,
            show_memory_usage=snap.status_check_show_memory,
        )
