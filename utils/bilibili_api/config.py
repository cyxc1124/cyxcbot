"""
B站API配置模块
提供B站API相关的配置管理功能
"""

import os
from nonebot.log import logger


class BilibiliConfig:
    """B站API配置管理类"""

    @staticmethod
    def get_bilibili_cookie() -> str:
        """从环境变量读取B站Cookie配置"""
        try:
            cookie = os.getenv('BILIBILI_COOKIE', '')
            if cookie:
                logger.info("加载B站Cookie配置")
            return cookie
        except Exception as e:
            logger.error(f"读取B站Cookie配置失败: {e}")
            return ""