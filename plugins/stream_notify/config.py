from pydantic import BaseModel, Field
from typing import List
import os


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

# 添加调试打印
print("=== 插件配置调试信息 ===")
print(f"环境变量 STREAM_NOTIFY_NOTIFY_GROUPS: {repr(os.environ.get('STREAM_NOTIFY_NOTIFY_GROUPS'))}")
print(f"环境变量 STREAM_NOTIFY_INCLUDE_ROOM_INFO: {repr(os.environ.get('STREAM_NOTIFY_INCLUDE_ROOM_INFO'))}")
print("=== 配置调试信息结束 ===") 