"""
截图功能模块
提供网页截图功能，支持B站动态等页面截图
"""

from .screenshot import (
    DynamicScreenshot,
    close_screenshot_service,
    get_dynamic_screenshot,
    init_screenshot_service,
)

__all__ = [
    "get_dynamic_screenshot",
    "init_screenshot_service",
    "close_screenshot_service",
    "DynamicScreenshot",
]
