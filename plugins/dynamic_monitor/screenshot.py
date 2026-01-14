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

    async def get_dynamic_screenshot_pc(self, dynamic_id: int, page: Page):
        """PC端动态截图 - 使用桌面版页面获得更好质量"""
        url = f"https://t.bilibili.com/{dynamic_id}"
        logger.info(f"开始PC端截图动态 {dynamic_id}, 请求URL: {url}")

        try:
            # 设置PC端视口 - 使用标准桌面分辨率
            await page.set_viewport_size({
                "width": 1920,
                "height": 1080,
                "device_scale_factor": 1  # PC端通常不需要高DPI缩放
            })

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

            # 等待页面完全加载
            await page.wait_for_load_state(state="domcontentloaded", timeout=10000)

            # 等待并检查动态内容区域 - PC端选择器
            dynamic_selectors = [
                ".bili-dyn-item",  # 完整动态卡片 - 优先级最高
                ".card",  # PC端主要卡片
                ".dynamic-card",  # 动态卡片
                ".bili-dyn-item__card",  # 新版动态卡片
                ".bili-dyn-list__item",  # 动态列表项
                "[class*='card']",  # 包含card的元素
                ".opus-modules",  # 兼容旧版
                ".dyn-card"  # 通用动态卡片
            ]

            dynamic_found = False
            for selector in dynamic_selectors:
                try:
                    await page.wait_for_selector(selector, state="visible", timeout=8000)
                    logger.debug(f"找到动态内容元素: {selector}")
                    dynamic_found = True
                    break
                except Exception:
                    continue

            if not dynamic_found:
                logger.warning(f"未找到动态内容元素，继续执行截图")

            # 轻微滚动页面以触发懒加载内容
            try:
                await page.evaluate("window.scrollTo(0, 100)")
                await page.wait_for_timeout(500)
                await page.evaluate("window.scrollTo(0, 0)")
                logger.debug("页面滚动完成，触发懒加载")
            except Exception as e:
                logger.warning(f"页面滚动失败: {e}")

            # PC端样式处理
            try:
                await page.add_script_tag(path=mobile_js)
                await page.evaluate("setFont()")
                logger.debug(f"动态 {dynamic_id} 样式设置完成")
            except Exception as e:
                logger.warning(f"样式设置失败: {e}")

            # 等待更长时间让内容完全渲染
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception as e:
                logger.warning(f"等待网络空闲超时: {e}")

            # 等待动态内容可能的变化
            await page.wait_for_timeout(1000)  # 等待1秒让内容稳定

            # 再次检查是否有新内容加载
            try:
                await page.evaluate("""
                    // 等待可能的异步内容加载
                    return new Promise(resolve => {
                        let checkCount = 0;
                        const checkInterval = setInterval(() => {
                            checkCount++;
                            const cards = document.querySelectorAll('.bili-dyn-item, .card, .dynamic-card, .bili-dyn-item__card');
                            if (cards.length > 0 || checkCount > 10) {
                                clearInterval(checkInterval);
                                resolve(true);
                            }
                        }, 200);
                    });
                """)
                logger.debug("异步内容加载检查完成")
            except Exception as e:
                logger.warning(f"异步内容检查失败: {e}")

            # 最终等待，确保页面稳定
            await page.wait_for_timeout(500)

            # 获取动态卡片，PC端选择器 - 优先选择完整动态卡片
            card = None
            selectors = [
                ".bili-dyn-item",  # 完整动态卡片 - 优先级最高
                ".card",  # PC端主要卡片
                ".dynamic-card",  # 动态卡片
                ".bili-dyn-item__card",  # 新版动态卡片
                ".bili-dyn-list__item",  # 动态列表项
                "[class*='card']",  # 包含card的元素
                ".opus-modules"  # 兼容移动端
            ]

            for selector in selectors:
                try:
                    card = await page.query_selector(selector)
                    if card:
                        break
                except Exception:
                    continue

            if not card:
                raise Exception("未找到动态内容区域")

            # 获取边界框 - 不限制分辨率，获取完整内容
            clip = await card.bounding_box()
            if not clip or clip["width"] == 0 or clip["height"] == 0:
                raise Exception("无法获取动态区域边界")

            logger.debug(f"动态 {dynamic_id} 内容区域大小: {clip['width']}x{clip['height']}")

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
                page, clip = await self.get_dynamic_screenshot_pc(dynamic_id, page)

                # 截图
                logger.debug(f"正在截图动态 {dynamic_id}, 区域大小: {clip['width']}x{clip['height']}")
                screenshot = await page.screenshot(
                    clip=clip,
                    type="jpeg",
                    quality=100  # 最高JPEG质量
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
            url = f"https://t.bilibili.com/{dynamic_id}"
            logger.info(f"开始PC端简化截图动态 {dynamic_id}, 请求URL: {url}")

            # PC端页面加载 - 使用标准桌面视口
            await page.set_viewport_size({
                "width": 1920,
                "height": 1080,
                "device_scale_factor": 1
            })
            logger.debug(f"简化截图: 正在加载页面 {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # 检查404
            if "404" in page.url:
                raise Notfound("动态不存在")

            # 等待页面基本加载
            await page.wait_for_load_state("domcontentloaded", timeout=5000)

            # 简化版也添加滚动和等待逻辑
            try:
                await page.evaluate("window.scrollTo(0, 100)")
                await page.wait_for_timeout(300)
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception as e:
                logger.warning(f"简化截图滚动失败: {e}")

            # 等待内容稳定
            await page.wait_for_timeout(800)

            # 直接截取整个可见区域（简化方案）
            logger.debug(f"简化截图: 正在截取可见区域")
            screenshot = await page.screenshot(
                type="jpeg",
                quality=100,  # 最高质量设置
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