from pydantic import BaseModel, Field
from typing import List


class Config(BaseModel):
    """B站直播通知插件配置"""
    
    # 需要发送通知的群组ID列表（可通过环境变量 NOTIFY_GROUPS 配置）
    notify_groups: List[str] = Field(
        # default=["591116063", "993692376", "364477847"],
        default=["123456789"],
        description="需要发送通知的群组ID列表"
    )
    
    # 是否包含房间信息（可通过环境变量 INCLUDE_ROOM_INFO 配置）
    include_room_info: bool = Field(
        default=True,
        description="是否包含房间信息（标题、链接等）"
    )

    model_config = {
        "env_prefix": "",  # 无前缀，直接读取环境变量
        "env_file": ".env",  # 从.env文件读取
        "env_file_encoding": "utf-8"
    } 