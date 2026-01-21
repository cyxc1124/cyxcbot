"""
共享工具模块
提供项目级别的通用功能
"""

# B站API相关
from .bilibili_api import DynamicFetcher, DynamicItem

__all__ = [
    'DynamicFetcher',
    'DynamicItem',
]