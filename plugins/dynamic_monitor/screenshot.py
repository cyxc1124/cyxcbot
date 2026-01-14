"""
动态截图功能模块
负责获取B站动态的网页截图
基于HarukaBot的实现
"""

import asyncio
from pathlib import Path
from typing import Optional, Tuple
from nonebot.log import logger

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright未安装，动态截图功能将被禁用")


class Notfound(Exception):
    """动态不存在异常"""
    pass


# mobile.js 文件路径
mobile_js = Path(__file__).parent.joinpath("mobile.js")


async def fill_font(route):
    """字体路由处理"""
    await route.fulfill(
        content_type="font/woff2",
        body=b''  # 返回空字体
    )


async def init_browser(proxy=None, **kwargs) -> BrowserContext:
    """初始化浏览器"""
    logger.info("初始化浏览器")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
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
        ],
        proxy={"server": proxy} if proxy else None,
        **kwargs
    )
    context = await browser.new_context(
        viewport={"width": 460, "height": 780},  # 移动端尺寸
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
    )
    return context


class DynamicScreenshot:
    """动态截图器"""

    def __init__(self):
        self.browser_context: Optional[BrowserContext] = None

    async def init_browser(self):
        """初始化浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("playwright不可用，无法初始化浏览器")
            return False

        try:
            self.browser_context = await init_browser()
            logger.info("浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            return False

    async def close_browser(self):
        """关闭浏览器"""
        try:
            if self.browser_context:
                await self.browser_context.close()
                self.browser_context = None
            logger.info("浏览器已关闭")
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")

    async def get_dynamic_screenshot_mobile(self, dynamic_id: int, page: Page):
        """移动端动态截图 - 基于HarukaBot实现"""
        url = f"https://m.bilibili.com/dynamic/{dynamic_id}"

        # 设置视口
        await page.set_viewport_size({"width": 460, "height": 780})

        # 设置字体路由拦截
        await page.route(re.compile(r"^https://static\.graiax\.fonts/(.+)$"), fill_font)

        # 导航到页面
        await page.goto(url, wait_until="networkidle")

        # 检查是否为404页面
        if page.url == "https://m.bilibili.com/404":
            raise Notfound("动态不存在")

        # 等待页面加载
        await page.wait_for_load_state(state="domcontentloaded")

        # 等待关键元素出现
        await page.wait_for_selector(".b-img__inner, .dyn-header__author__face", state="visible")

        # 注入移动端样式处理脚本
        await page.add_script_tag(path=mobile_js)

        # 设置字体（使用默认设置）
        await page.evaluate("setFont()")

        # 等待样式处理完成
        await page.wait_for_function("getMobileStyle(false)")

        # 等待加载完成
        await page.wait_for_load_state("networkidle")
        await page.wait_for_load_state("domcontentloaded")

        # 等待字体和图片加载完成
        await page.wait_for_timeout(1000)  # 等待1秒

        # 判断字体和图片是否加载完成
        need_wait = ["imageComplete", "fontsLoaded"]
        await asyncio.gather(*[page.wait_for_function(f"{i}()") for i in need_wait])

        # 获取动态卡片
        # 检查是否为新版动态(opus)
        card_selector = ".opus-modules" if "opus" in page.url else ".dyn-card"
        card = await page.query_selector(card_selector)

        if not card:
            raise Exception("未找到动态内容")

        # 获取边界框
        clip = await card.bounding_box()
        if not clip:
            raise Exception("无法获取动态区域")

        return page, clip

    async def get_dynamic_screenshot(self, dynamic_id: int, timeout: int = 30000) -> Tuple[Optional[bytes], Optional[str]]:
        """
        获取动态截图

        Args:
            dynamic_id: 动态ID
            timeout: 超时时间（毫秒）

        Returns:
            Tuple[图片bytes, 错误信息]
        """
        if not self.browser_context:
            return None, "浏览器未初始化"

        page = None
        try:
            page = await self.browser_context.new_page()
            page.set_default_timeout(timeout)

            # 使用移动端截图方法
            page, clip = await self.get_dynamic_screenshot_mobile(dynamic_id, page)

            # 截图
            screenshot = await page.screenshot(
                clip=clip,
                type="jpeg",
                quality=85
            )

            return screenshot, None

        except Notfound:
            logger.warning(f"动态 {dynamic_id} 不存在")
            return None, "动态不存在"
        except Exception as e:
            error_msg = f"截图失败: {str(e)}"
            logger.warning(f"动态{dynamic_id}截图失败: {error_msg}")
            return None, error_msg

        finally:
            if page:
                try:
                    await page.close()
                except Exception as close_error:
                    logger.warning(f"关闭页面时出错: {close_error}")


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
    if not dynamic_screenshot.browser_context:
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