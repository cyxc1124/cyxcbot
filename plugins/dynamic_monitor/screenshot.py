"""
动态截图功能模块
负责获取B站动态的网页截图
基于HarukaBot的实现
"""

import asyncio
import re
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
        logger.info(f"开始截图动态 {dynamic_id}, 请求URL: {url}")

        try:
            # 设置视口
            await page.set_viewport_size({"width": 460, "height": 780})

            # 设置字体路由拦截
            await page.route(re.compile(r"^https://static\.graiax\.fonts/(.+)$"), fill_font)

            # 设置页面超时
            page.set_default_timeout(30000)  # 30秒超时

            # 导航到页面，使用更稳定的等待条件
            logger.debug(f"正在加载页面: {url}")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            if not response or response.status != 200:
                logger.error(f"页面加载失败: HTTP {response.status if response else 'unknown'}, URL: {url}")
                raise Exception(f"页面加载失败: HTTP {response.status if response else 'unknown'}")

            # 检查是否为404页面
            current_url = page.url
            logger.debug(f"页面跳转到: {current_url}")
            if "404" in current_url or page.url == "https://m.bilibili.com/404":
                logger.warning(f"动态 {dynamic_id} 不存在，当前URL: {current_url}")
                raise Notfound("动态不存在")

            # 等待页面加载完成
            await page.wait_for_load_state(state="domcontentloaded", timeout=10000)

            # 等待关键元素出现，使用更宽松的选择器
            try:
                await page.wait_for_selector(
                    ".b-img__inner, .dyn-header__author__face, .dyn-card, .opus-modules",
                    state="visible",
                    timeout=15000
                )
                logger.debug(f"动态 {dynamic_id} 关键元素加载完成")
            except Exception as e:
                logger.warning(f"等待元素超时，但继续执行: {e}, URL: {url}")

            # 注入移动端样式处理脚本
            try:
                await page.add_script_tag(path=mobile_js)
                logger.debug(f"动态 {dynamic_id} 样式脚本注入完成")
            except Exception as e:
                logger.warning(f"注入样式脚本失败: {e}, mobile.js路径: {mobile_js}")

            # 设置字体（使用默认设置）
            try:
                await page.evaluate("setFont()")
            except Exception as e:
                logger.warning(f"设置字体失败: {e}")

            # 等待样式处理完成
            try:
                await page.wait_for_function("typeof getMobileStyle === 'function'", timeout=5000)
                await page.evaluate("getMobileStyle(false)")
            except Exception as e:
                logger.warning(f"样式处理失败: {e}")

            # 等待加载完成
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                logger.warning(f"等待网络空闲超时: {e}")

            # 等待字体和图片加载完成（缩短等待时间）
            await page.wait_for_timeout(500)  # 等待0.5秒

            # 获取动态卡片，尝试多种选择器
            card = None
            selectors = [".opus-modules", ".dyn-card", ".bili-dyn-item", "[class*='dyn']"]

            for selector in selectors:
                try:
                    card = await page.query_selector(selector)
                    if card:
                        break
                except Exception:
                    continue

            if not card:
                raise Exception("未找到动态内容区域")

            # 获取边界框
            clip = await card.bounding_box()
            if not clip or clip["width"] == 0 or clip["height"] == 0:
                raise Exception("无法获取动态区域边界")

            return page, clip

        except Exception as e:
            # 记录详细的错误信息
            logger.error(f"动态{dynamic_id}截图处理失败: {str(e)}")
            raise

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

            # 首先尝试完整版截图
            try:
                page, clip = await self.get_dynamic_screenshot_mobile(dynamic_id, page)

                # 截图
                logger.debug(f"正在截图动态 {dynamic_id}, 区域大小: {clip['width']}x{clip['height']}")
                screenshot = await page.screenshot(
                    clip=clip,
                    type="jpeg",
                    quality=85
                )
                screenshot_size = len(screenshot) if screenshot else 0
                logger.info(f"动态 {dynamic_id} 截图成功，大小: {screenshot_size} bytes")

                return screenshot, None

            except Exception as full_screenshot_error:
                logger.warning(f"完整截图失败，尝试简化截图: {full_screenshot_error}")

                # 如果完整截图失败，尝试简化截图
                try:
                    return await self.get_dynamic_screenshot_simple(dynamic_id, page)
                except Exception as simple_error:
                    logger.error(f"简化截图也失败: {simple_error}")
                    return None, f"截图失败: {str(full_screenshot_error)}"

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

    async def get_dynamic_screenshot_simple(self, dynamic_id: int, page: Page) -> Tuple[Optional[bytes], Optional[str]]:
        """简化版动态截图 - 当完整截图失败时的备选方案"""
        try:
            url = f"https://m.bilibili.com/dynamic/{dynamic_id}"
            logger.info(f"开始简化截图动态 {dynamic_id}, 请求URL: {url}")

            # 简单的页面加载
            await page.set_viewport_size({"width": 360, "height": 640})
            logger.debug(f"简化截图: 正在加载页面 {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # 检查404
            if "404" in page.url:
                raise Notfound("动态不存在")

            # 等待页面基本加载
            await page.wait_for_load_state("domcontentloaded", timeout=5000)

            # 直接截取整个可见区域（简化方案）
            logger.debug(f"简化截图: 正在截取可见区域")
            screenshot = await page.screenshot(
                type="jpeg",
                quality=80,
                full_page=False  # 只截取可见区域
            )

            screenshot_size = len(screenshot) if screenshot else 0
            logger.info(f"使用简化截图成功获取动态 {dynamic_id}, 大小: {screenshot_size} bytes")
            return screenshot, None

        except Exception as e:
            logger.error(f"简化截图也失败: {str(e)}")
            raise


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
    logger.debug(f"请求获取动态 {dynamic_id} 截图")

    # 如果浏览器未初始化，尝试初始化
    if not dynamic_screenshot.browser_context:
        logger.info(f"为动态 {dynamic_id} 初始化浏览器")
        success = await dynamic_screenshot.init_browser()
        if not success:
            logger.error("浏览器初始化失败")
            return None, "浏览器初始化失败"

    result = await dynamic_screenshot.get_dynamic_screenshot(dynamic_id)
    if result[1]:  # 如果有错误
        logger.warning(f"动态 {dynamic_id} 截图失败: {result[1]}")
    else:
        logger.debug(f"动态 {dynamic_id} 截图请求完成")
    return result


async def init_screenshot_service():
    """初始化截图服务"""
    global dynamic_screenshot
    await dynamic_screenshot.init_browser()


async def close_screenshot_service():
    """关闭截图服务"""
    global dynamic_screenshot
    await dynamic_screenshot.close_browser()