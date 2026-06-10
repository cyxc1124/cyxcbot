"""
B站API配置模块
提供B站API相关的配置管理功能
"""

from nonebot.log import logger


class BilibiliConfig:
    """B站API配置管理类"""

    @staticmethod
    def get_bilibili_cookie() -> str:
        """从 ConfigService 读取 B 站 Cookie"""
        try:
            from shared.config.service import get_config_service

            cookie = get_config_service().get_snapshot().bilibili_cookie
            if cookie:
                logger.debug("已加载 B 站 Cookie")
            return cookie or ""
        except Exception as e:
            logger.error(f"读取 B 站 Cookie 配置失败: {e}")
            return ""
