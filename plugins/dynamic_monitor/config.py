from pydantic import BaseModel, Field
from typing import List, Dict
import os
import json
from nonebot.log import logger
from utils.bilibili_api import BilibiliConfig


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



    # 是否启用动态截图
    enable_dynamic_screenshot: bool = Field(
        default_factory=lambda: Config._get_enable_dynamic_screenshot(),
        description="是否在推送消息中包含动态截图"
    )

    # B站Cookie配置
    bilibili_cookie: str = Field(
        default_factory=lambda: BilibiliConfig.get_bilibili_cookie(),
        description="B站用户Cookie，用于提高API请求成功率"
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
                # 确保间隔在合理范围内（10秒到1小时）
                return max(10, min(3600, interval))
            # 默认值：30秒
            return 30
        except (ValueError, TypeError):
            return 30



    @staticmethod
    def _get_enable_dynamic_screenshot() -> bool:
        """从环境变量读取是否启用动态截图配置"""
        try:
            # 从环境变量读取
            enable_screenshot_str = os.getenv('DYNAMIC_ENABLE_SCREENSHOT')
            if enable_screenshot_str:
                return json.loads(enable_screenshot_str.lower())
            # 默认值：启用截图
            return True
        except (json.JSONDecodeError, TypeError):
            return True

    def get_uids_by_group_id(self, group_id: str) -> List[str]:
        """根据群组ID反向查找对应的UP主UID列表

        Args:
            group_id: 群组ID

        Returns:
            该群组对应的UP主UID列表
        """
        uids = []
        for uid, group_ids in self.dynamic_monitor_mapping.items():
            if group_id in group_ids:
                uids.append(uid)
        return uids

    model_config = {
        "env_prefix": "",  # 无前缀，直接读取环境变量
        "env_file": ".env",  # 从.env文件读取
        "env_file_encoding": "utf-8"
    }