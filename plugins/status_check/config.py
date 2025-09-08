from pydantic import BaseModel, Field
from typing import List
import os
import json


class Config(BaseModel):
    """状态查询插件配置"""
    
    # 允许查询状态的QQ号列表（可通过环境变量 STATUS_CHECK_ALLOWED_QQ 配置）
    allowed_qq_numbers: List[int] = Field(
        default_factory=lambda: Config._get_allowed_qq_numbers(),
        description="允许查询状态的QQ号列表"
    )
    
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
    def _get_allowed_qq_numbers() -> List[int]:
        """从环境变量读取允许查询的QQ号配置，优先使用SUPERUSERS"""
        try:
            # 优先使用SUPERUSERS配置
            superusers_str = os.getenv('SUPERUSERS')
            if superusers_str:
                superusers = json.loads(superusers_str)
                # 转换为int列表
                return [int(qq) for qq in superusers]
            
            # 其次使用专用的环境变量
            allowed_qq_str = os.getenv('STATUS_CHECK_ALLOWED_QQ')
            if allowed_qq_str:
                return json.loads(allowed_qq_str)
                
            # 如果都没有配置，返回空列表（只允许SUPERUSER权限访问）
            return []
        except (json.JSONDecodeError, TypeError, ValueError):
            # 配置解析失败时返回空列表
            return []
    
    @staticmethod
    def _get_show_detailed_status() -> bool:
        """从环境变量读取是否显示详细状态信息"""
        try:
            detailed_str = os.getenv('STATUS_CHECK_SHOW_DETAILED', 'true')
            return detailed_str.lower() in ['true', '1', 'yes']
        except:
            return True
    
    @staticmethod
    def _get_show_uptime() -> bool:
        """从环境变量读取是否显示运行时间"""
        try:
            uptime_str = os.getenv('STATUS_CHECK_SHOW_UPTIME', 'true')
            return uptime_str.lower() in ['true', '1', 'yes']
        except:
            return True
    
    @staticmethod
    def _get_show_memory_usage() -> bool:
        """从环境变量读取是否显示内存使用情况"""
        try:
            memory_str = os.getenv('STATUS_CHECK_SHOW_MEMORY', 'true')
            return memory_str.lower() in ['true', '1', 'yes']
        except:
            return True

    model_config = {
        "env_prefix": "",  # 无前缀，直接读取环境变量
        "env_file": ".env",  # 从.env文件读取
        "env_file_encoding": "utf-8"
    } 