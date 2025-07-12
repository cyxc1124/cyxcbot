from pydantic import BaseModel, Field
from typing import List
import os
import json


class Config(BaseModel):
    """B站直播通知插件配置"""
    
    # 需要发送通知的群组ID列表（可通过环境变量 NOTIFY_GROUPS 配置）
    notify_groups: List[str] = Field(
        default_factory=lambda: Config._get_notify_groups(),
        description="需要发送通知的群组ID列表"
    )
    
    # 是否包含房间信息（可通过环境变量 INCLUDE_ROOM_INFO 配置）
    include_room_info: bool = Field(
        default_factory=lambda: Config._get_include_room_info(),
        description="是否包含房间信息（标题、链接等）"
    )

    @staticmethod
    def _get_notify_groups() -> List[str]:
        """从环境变量读取通知群组配置"""
        try:
            # 优先从环境变量读取
            notify_groups_str = os.getenv('NOTIFY_GROUPS')
            if notify_groups_str:
                return json.loads(notify_groups_str)
            # 默认值
            return ["123456789"]
        except (json.JSONDecodeError, TypeError):
            return ["123456789"]
    
    @staticmethod
    def _get_include_room_info() -> bool:
        """从环境变量读取是否包含房间信息配置"""
        try:
            # 优先从环境变量读取
            include_room_info_str = os.getenv('INCLUDE_ROOM_INFO')
            if include_room_info_str:
                return json.loads(include_room_info_str.lower())
            # 默认值
            return True
        except (json.JSONDecodeError, TypeError):
            return True

    model_config = {
        "env_prefix": "",  # 无前缀，直接读取环境变量
        "env_file": ".env",  # 从.env文件读取
        "env_file_encoding": "utf-8"
    }
