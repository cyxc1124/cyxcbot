from pydantic import BaseModel, Field
from typing import List


class Config(BaseModel):
    """B站直播通知插件配置"""
    
    # 需要发送通知的群组ID列表（可通过环境变量 STREAM_NOTIFY_NOTIFY_GROUPS 配置）
    notify_groups: List[str] = Field(
        default=["123456789"],
        description="需要发送通知的群组ID列表"
    )
    
    # 是否包含房间信息（可通过环境变量 STREAM_NOTIFY_INCLUDE_ROOM_INFO 配置）
    include_room_info: bool = Field(
        default=True,
        description="是否包含房间信息（标题、链接等）"
    )

    class Config:
        env_prefix = "STREAM_NOTIFY_"  # 环境变量前缀
        env_file = ".env"  # 从.env文件读取
        env_file_encoding = "utf-8" 