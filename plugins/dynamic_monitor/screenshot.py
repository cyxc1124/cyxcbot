"""
动态截图功能模块
负责获取B站动态的网页截图
"""

import asyncio
from typing import Optional, Tuple
from nonebot.log import logger

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright未安装，动态截图功能将被禁用")


class DynamicScreenshot:
    """动态截图器"""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def init_browser(self):
        """初始化浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("playwright不可用，无法初始化浏览器")
            return False

        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu'
                ]
            )
            logger.info("浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            return False

    async def close_browser(self):
        """关闭浏览器"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("浏览器已关闭")
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")

    async def get_dynamic_screenshot(self, dynamic_id: int, timeout: int = 30000) -> Tuple[Optional[bytes], Optional[str]]:
        """
        获取动态截图

        Args:
            dynamic_id: 动态ID
            timeout: 超时时间（毫秒）

        Returns:
            Tuple[图片bytes, 错误信息]
        """
        if not self.browser:
            return None, "浏览器未初始化"

        url = f"https://m.bilibili.com/dynamic/{dynamic_id}"

        page: Optional[Page] = None
        try:
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": 360, "height": 640})  # 移动端尺寸

            # 设置超时
            page.set_default_timeout(timeout)

            # 导航到页面
            await page.goto(url, wait_until="networkidle")

            # 等待动态内容加载
            await page.wait_for_selector(".dynamic-card", timeout=10000)

            # 截取动态卡片区域
            card = await page.query_selector(".dynamic-card")
            if not card:
                return None, "未找到动态内容"

            # 获取卡片边界
            bbox = await card.bounding_box()
            if not bbox:
                return None, "无法获取动态区域"

            # 截图
            screenshot = await page.screenshot(
                clip={
                    "x": bbox["x"],
                    "y": bbox["y"],
                    "width": min(bbox["width"], 360),  # 限制宽度
                    "height": min(bbox["height"], 800)  # 限制高度
                },
                type="jpeg",
                quality=85
            )

            return screenshot, None

        except Exception as e:
            error_msg = f"截图失败: {str(e)}"
            logger.warning(f"动态{dynamic_id}截图失败: {error_msg}")
            return None, error_msg

        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass


# 全局截图器实例
dynamic_screenshot = DynamicScreenshot()


async def get_dynamic_screenshot(dynamic_id: int) -> Tuple[Optional[bytes], Optional[str]]:
    """
    获取动态截图的便捷函数

    Args:
        dynamic_id: 动态ID

    Returns:
        Tuple[图片bytes, 错误信息]
    """
    global dynamic_screenshot

    # 如果浏览器未初始化，尝试初始化
    if not dynamic_screenshot.browser:
        success = await dynamic_screenshot.init_browser()
        if not success:
            return None, "浏览器初始化失败"

    return await dynamic_screenshot.get_dynamic_screenshot(dynamic_id)


async def init_screenshot_service():
    """初始化截图服务"""
    global dynamic_screenshot
    await dynamic_screenshot.init_browser()


async def close_screenshot_service():
    """关闭截图服务"""
    global dynamic_screenshot
    await dynamic_screenshot.close_browser()