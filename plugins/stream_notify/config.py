from pydantic import BaseModel, Field
from typing import List, Dict
import os
import json


class Config(BaseModel):
    """B站直播通知插件配置"""
    
    # 房间号-群组映射配置（可通过环境变量 STREAMER_GROUP_MAPPING 配置）
    streamer_group_mapping: Dict[str, List[str]] = Field(
        default_factory=lambda: Config._get_streamer_group_mapping(),
        description="房间号-群组ID映射配置"
    )
    
    # 是否包含房间信息（可通过环境变量 INCLUDE_ROOM_INFO 配置）
    include_room_info: bool = Field(
        default_factory=lambda: Config._get_include_room_info(),
        description="是否包含房间信息（标题、链接等）"
    )

    @staticmethod
    def _get_streamer_group_mapping() -> Dict[str, List[str]]:
        """从环境变量读取房间号-群组映射配置"""
        try:
            # 从环境变量读取
            mapping_str = os.getenv('STREAMER_GROUP_MAPPING')
            if mapping_str:
                mapping = json.loads(mapping_str)
                # 确保所有键都是字符串，所有值都是字符串列表
                if isinstance(mapping, dict):
                    return {str(k): [str(gid) for gid in v] if isinstance(v, list) else [] 
                            for k, v in mapping.items()}
            # 如果没有配置，返回空字典
            return {}
        except (json.JSONDecodeError, TypeError) as e:
            # 配置解析失败时返回空字典并记录错误
            print(f"解析 STREAMER_GROUP_MAPPING 配置失败: {e}")
            return {}
    
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
