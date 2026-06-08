from pydantic import BaseModel, Field
import os
import json


class Config(BaseModel):
    """状态查询插件配置"""

    # 是否显示详细状态信息
    show_detailed_status: bool = Field(
        default_factory=lambda: Config._get_show_detailed_status(),
        description="是否显示详细状态信息"
    )
    
    # 是否显示机器人运行时间
    show_uptime: bool = Field(
        default_factory=lambda: Config._get_show_uptime(),
        description="是否显示机器人运行时间"
    )
    
    # 是否显示内存使用情况
    show_memory_usage: bool = Field(
        default_factory=lambda: Config._get_show_memory_usage(),
        description="是否显示内存使用情况"
    )

    @staticmethod
    def _get_show_detailed_status() -> bool:
        """从环境变量读取是否显示详细状态信息"""
        try:
            detailed_str = os.getenv('STATUS_CHECK_SHOW_DETAILED')
            if detailed_str:
                return json.loads(detailed_str.lower())
            # 默认值
            return True
        except (json.JSONDecodeError, TypeError):
            return True
    
    @staticmethod
    def _get_show_uptime() -> bool:
        """从环境变量读取是否显示运行时间"""
        try:
            uptime_str = os.getenv('STATUS_CHECK_SHOW_UPTIME')
            if uptime_str:
                return json.loads(uptime_str.lower())
            # 默认值
            return True
        except (json.JSONDecodeError, TypeError):
            return True
    
    @staticmethod
    def _get_show_memory_usage() -> bool:
        """从环境变量读取是否显示内存使用情况"""
        try:
            memory_str = os.getenv('STATUS_CHECK_SHOW_MEMORY')
            if memory_str:
                return json.loads(memory_str.lower())
            # 默认值
            return True
        except (json.JSONDecodeError, TypeError):
            return True

    model_config = {
        "env_prefix": "",  # 无前缀，直接读取环境变量
        "env_file": ".env",  # 从.env文件读取
        "env_file_encoding": "utf-8"
    } 