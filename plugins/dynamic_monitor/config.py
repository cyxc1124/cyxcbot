from pydantic import BaseModel, Field
from typing import List, Dict
import os
import json
from nonebot.log import logger


class Config(BaseModel):
    """UP主动态监控插件配置"""

    # UP主UID-群组映射配置（可通过环境变量 DYNAMIC_MONITOR_MAPPING 配置）
    dynamic_monitor_mapping: Dict[str, List[str]] = Field(
        default_factory=lambda: Config._get_dynamic_monitor_mapping(),
        description="UP主UID-群组ID映射配置"
    )

    # 监控间隔时间（秒）
    monitor_interval: int = Field(
        default_factory=lambda: Config._get_monitor_interval(),
        description="监控间隔时间（秒）"
    )

    # 是否包含动态详情
    include_dynamic_details: bool = Field(
        default_factory=lambda: Config._get_include_dynamic_details(),
        description="是否包含动态详情（内容、图片等）"
    )

    @staticmethod
    def _get_dynamic_monitor_mapping() -> Dict[str, List[str]]:
        """从环境变量读取UP主UID-群组映射配置"""
        try:
            # 从环境变量读取
            mapping_str = os.getenv('DYNAMIC_MONITOR_MAPPING')
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
            logger.error(f"解析 DYNAMIC_MONITOR_MAPPING 配置失败: {e}")
            return {}

    @staticmethod
    def _get_monitor_interval() -> int:
        """从环境变量读取监控间隔时间"""
        try:
            interval_str = os.getenv('DYNAMIC_MONITOR_INTERVAL')
            if interval_str:
                interval = int(interval_str)
                # 确保间隔在合理范围内（30秒到1小时）
                return max(30, min(3600, interval))
            # 默认值：5分钟
            return 300
        except (ValueError, TypeError):
            return 300

    @staticmethod
    def _get_include_dynamic_details() -> bool:
        """从环境变量读取是否包含动态详情配置"""
        try:
            # 优先从环境变量读取
            include_details_str = os.getenv('DYNAMIC_INCLUDE_DETAILS')
            if include_details_str:
                return json.loads(include_details_str.lower())
            # 默认值
            return True
        except (json.JSONDecodeError, TypeError):
            return True

    model_config = {
        "env_prefix": "",  # 无前缀，直接读取环境变量
        "env_file": ".env",  # 从.env文件读取
        "env_file_encoding": "utf-8"
    }