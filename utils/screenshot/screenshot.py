"""
动态截图功能模块
负责获取B站动态的网页截图
基于HarukaBot的实现
"""

from typing import Optional, Tuple
from nonebot.log import logger

try:
    from playwright.async_api import async_playwright, Page, BrowserContext
    from playwright_stealth import Stealth
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright未安装，动态截图功能将被禁用")


class Notfound(Exception):
    """动态不存在异常"""
    pass


def _parse_cookie_string(cookie_str: str) -> list:
    """将Cookie字符串解析为Playwright所需的Cookie列表"""
    cookies = []
    for item in cookie_str.split("; "):
        if "=" in item:
            name, value = item.split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".bilibili.com",
                "path": "/",
            })
    return cookies


async def init_browser(proxy=None, **kwargs) -> BrowserContext:
    """初始化浏览器 - 最佳实践配置"""
    logger.info("初始化Playwright浏览器")

    playwright = await async_playwright().start()

    # 优化的浏览器启动参数
    browser_args = [
        '--no-sandbox',                    # 禁用沙盒（Docker环境必需）
        '--disable-setuid-sandbox',        # 禁用setuid沙盒
        '--disable-dev-shm-usage',         # 禁用/dev/shm使用
        '--disable-accelerated-2d-canvas', # 禁用硬件加速画布
        '--no-first-run',                  # 跳过首次运行设置
        '--no-zygote',                     # 禁用zygote进程
        '--disable-gpu',                   # 禁用GPU硬件加速
        '--disable-web-security',          # 禁用同源策略（如果需要）
        '--disable-features=VizDisplayCompositor', # 禁用显示合成器
        #'--disable-extensions',            # 禁用扩展
        #'--disable-plugins',               # 禁用插件
        #'--disable-images',                # 不加载图片（可选，加快加载）
        #'--disable-javascript',            # 不执行JS（但我们需要JS，所以不加）
        '--disable-background-timer-throttling', # 禁用后台定时器限制
        '--disable-backgrounding-occluded-windows', # 禁用后台窗口限制
        '--disable-renderer-backgrounding', # 禁用渲染器后台化
    ]

    browser = await playwright.chromium.launch(
        headless=True,
        args=browser_args,
        proxy={"server": proxy} if proxy else None,
        # 内存和性能优化
        handle_sigint=False,
        handle_sigterm=False,
        handle_sighup=False,
        **kwargs
    )

    # 创建优化的浏览器上下文 - 高质量截图配置
    context = await browser.new_context(
        # 高分辨率视口设置
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        # 高质量渲染设置
        ignore_https_errors=True,  # 忽略HTTPS错误
        bypass_csp=True,          # 绕过内容安全策略
        # 禁用不必要的资源加载以提高性能
        permissions=[],           # 不授予任何权限
        # 高质量渲染选项
        device_scale_factor=2,    # 默认2倍缩放，提高清晰度
        is_mobile=False,          # PC模式
        has_touch=False,          # 非触摸设备
    )

    # 注入B站Cookie
    from utils.bilibili_api.config import BilibiliConfig
    cookie_str = BilibiliConfig.get_bilibili_cookie()
    if cookie_str:
        cookies = _parse_cookie_string(cookie_str)
        await context.add_cookies(cookies)
        logger.info(f"已注入 {len(cookies)} 个B站Cookie")
    else:
        logger.warning("未登录 B 站，截图可能触发验证码")

    logger.info("浏览器初始化完成")
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
            # 设置PC端视口 - 高清分辨率以提高截图质量
            await page.set_viewport_size({
                "width": 1920,
                "height": 1080,
                "device_scale_factor": 2  # 2倍缩放，提高清晰度
            })

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
                ".bili-dyn-item",       # 完整动态卡片
                ".bili-dyn-item__main", # 主内容区域
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
                logger.warning("未找到动态内容元素，继续执行截图")

            # 轻微滚动页面以触发懒加载内容
            try:
                await page.evaluate("window.scrollTo(0, 100)")
                await page.wait_for_timeout(500)
                await page.evaluate("window.scrollTo(0, 0)")
                logger.debug("页面滚动完成，触发懒加载")
            except Exception as e:
                logger.warning(f"页面滚动失败: {e}")

            # 等待更长时间让内容完全渲染
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception as e:
                logger.warning(f"等待网络空闲超时: {e}")

            # 等待动态内容可能的变化
            await page.wait_for_timeout(1000)  # 等待1秒让内容稳定

            # 再次检查是否有新内容加载
            try:
                await page.evaluate("""() => {
return new Promise(resolve => {
    let checkCount = 0;
    const checkInterval = setInterval(() => {
        checkCount++;
                const cards = document.querySelectorAll('.bili-dyn-item, .bili-dyn-item__main');
        if (cards.length > 0 || checkCount > 10) {
            clearInterval(checkInterval);
            resolve(true);
        }
    }, 200);
});
}""")
                logger.debug("异步内容加载检查完成")
            except Exception as e:
                logger.warning(f"异步内容检查失败: {e}")

            # 最终等待，确保页面稳定
            await page.wait_for_timeout(500)

            # 获取动态卡片，PC端选择器 - 优先选择完整动态卡片
            card = None
            selectors = [
                ".bili-dyn-item",       # 完整动态卡片
                ".bili-dyn-item__main", # 主内容区域
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
            await Stealth().apply_stealth_async(page)
            page.set_default_timeout(timeout)

            # 首先尝试完整版截图
            try:
                page, clip = await self.get_dynamic_screenshot_pc(dynamic_id, page)

                # 截图 - 使用PNG格式获得最佳质量（2倍缩放+无损压缩）
                logger.debug(f"正在截图动态 {dynamic_id}, 区域大小: {clip['width']}x{clip['height']}")
                screenshot = await page.screenshot(
                    clip=clip,
                    type="png",  # 改为PNG格式，无损压缩，保证最高质量
                    # PNG是无损格式，文件较大但质量最佳
                )
                screenshot_size = len(screenshot) if screenshot else 0
                logger.info(f"动态 {dynamic_id} 截图成功，大小: {screenshot_size} bytes")

                return screenshot, None

            except Exception as full_screenshot_error:
                logger.error(f"PC端截图失败: {full_screenshot_error}")
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