"""
B站直播监控插件配置
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import os
import json


class Config(BaseModel):
    """B站直播监控插件配置"""
    
    # 房间号-群组映射配置（可通过环境变量 LIVE_MONITOR_MAPPING 配置）
    # 格式: {"房间号": ["群号1", "群号2"], ...}
    live_monitor_mapping: Dict[str, List[str]] = Field(
        default_factory=lambda: Config._get_live_monitor_mapping(),
        description="房间号-群组ID映射配置"
    )
    
    # 监控间隔（秒），默认60秒，可通过环境变量 LIVE_MONITOR_INTERVAL 配置
    monitor_interval: int = Field(
        default_factory=lambda: Config._get_monitor_interval(),
        description="直播状态检查间隔（秒）"
    )
    
    # 是否包含房间详细信息（可通过环境变量 LIVE_MONITOR_INCLUDE_INFO 配置）
    include_room_info: bool = Field(
        default_factory=lambda: Config._get_include_room_info(),
        description="是否在通知中包含房间详细信息（标题、链接等）"
    )
    
    # B站 Cookie（可选，用于提高API稳定性）
    bilibili_cookie: Optional[str] = Field(
        default_factory=lambda: Config._get_bilibili_cookie(),
        description="B站用户Cookie（可选）"
    )
    
    # 是否启用 WebSocket 实时监控（默认启用）
    use_websocket: bool = Field(
        default_factory=lambda: Config._get_use_websocket(),
        description="是否启用 WebSocket 实时监控"
    )

    @staticmethod
    def _get_live_monitor_mapping() -> Dict[str, List[str]]:
        """从环境变量读取房间号-群组映射配置"""
        try:
            mapping_str = os.getenv('LIVE_MONITOR_MAPPING')
            if mapping_str:
                mapping = json.loads(mapping_str)
                if isinstance(mapping, dict):
                    return {str(k): [str(gid) for gid in v] if isinstance(v, list) else [] 
                            for k, v in mapping.items()}
            return {}
        except (json.JSONDecodeError, TypeError) as e:
            print(f"解析 LIVE_MONITOR_MAPPING 配置失败: {e}")
            return {}
    
    @staticmethod
    def _get_monitor_interval() -> int:
        """从环境变量读取监控间隔配置"""
        try:
            interval_str = os.getenv('LIVE_MONITOR_INTERVAL')
            if interval_str:
                return max(30, int(interval_str))  # 最小30秒
            return 60  # 默认60秒
        except (ValueError, TypeError):
            return 60
    
    @staticmethod
    def _get_include_room_info() -> bool:
        """从环境变量读取是否包含房间信息配置"""
        try:
            include_str = os.getenv('LIVE_MONITOR_INCLUDE_INFO')
            if include_str:
                return json.loads(include_str.lower())
            return True
        except (json.JSONDecodeError, TypeError):
            return True
    
    @staticmethod
    def _get_bilibili_cookie() -> Optional[str]:
        """从环境变量读取B站Cookie"""
        return os.getenv('BILIBILI_COOKIE')
    
    @staticmethod
    def _get_use_websocket() -> bool:
        """从环境变量读取是否启用WebSocket监控"""
        try:
            ws_str = os.getenv('LIVE_MONITOR_USE_WEBSOCKET')
            if ws_str:
                return json.loads(ws_str.lower())
            return True  # 默认启用
        except (json.JSONDecodeError, TypeError):
            return True

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }
