"""
视频查询插件配置
和动态监控共用 DYNAMIC_MONITOR_MAPPING 配置
"""

from pydantic import BaseModel, Field
from typing import List, Dict
import os
import json
from nonebot.log import logger
from utils.bilibili_api import BilibiliConfig


class Config(BaseModel):
    """视频查询插件配置"""

    # UP主UID-群组映射配置（和动态监控共用 DYNAMIC_MONITOR_MAPPING）
    dynamic_monitor_mapping: Dict[str, List[str]] = Field(
        default_factory=lambda: Config._get_dynamic_monitor_mapping(),
        description="UP主UID-群组ID映射配置"
    )

    # B站Cookie配置
    bilibili_cookie: str = Field(
        default_factory=lambda: BilibiliConfig.get_bilibili_cookie(),
        description="B站用户Cookie，用于提高API请求成功率"
    )

    @staticmethod
    def _get_dynamic_monitor_mapping() -> Dict[str, List[str]]:
        """从环境变量读取UP主UID-群组映射配置（和动态监控共用）"""
        try:
            mapping_str = os.getenv('DYNAMIC_MONITOR_MAPPING')
            if mapping_str:
                mapping = json.loads(mapping_str)
                if isinstance(mapping, dict):
                    return {str(k): [str(gid) for gid in v] if isinstance(v, list) else []
                            for k, v in mapping.items()}
            return {}
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"解析 DYNAMIC_MONITOR_MAPPING 配置失败: {e}")
            return {}

    def get_uids_by_group_id(self, group_id: str) -> List[str]:
        """根据群组ID反向查找对应的UP主UID列表"""
        uids = []
        for uid, group_ids in self.dynamic_monitor_mapping.items():
            if group_id in group_ids:
                uids.append(uid)
        return uids

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }
