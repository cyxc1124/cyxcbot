"""
动态截图功能模块
负责获取 B 站动态/opus 页面的网页截图
"""

from typing import List, Optional, Tuple

from nonebot.log import logger

try:
    from playwright.async_api import (
        BrowserContext,
        ElementHandle,
        Page,
        async_playwright,
    )
    from playwright_stealth import Stealth

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright未安装，动态截图功能将被禁用")

DYNAMIC_CARD_SELECTORS: List[str] = [
    ".bili-opus-view",
    ".bili-dyn-item",
    ".opus-detail",
    ".bili-dyn-item__main",
]

DYNAMIC_CONTENT_WAIT_SELECTORS: List[str] = [
    ".bili-opus-view",
    ".bili-dyn-item",
    ".opus-detail",
    ".bili-dyn-item__main",
]

DYNAMIC_UNCLIP_SELECTORS = (
    ".bili-opus-view, .opus-detail, .opus-module-content, .opus-module, "
    ".bili-dyn-item, .bili-dyn-item__main, .bili-dyn-content, "
    ".bili-dyn-content__text, .bili-dyn-item__body"
)


class Notfound(Exception):
    """动态不存在异常"""

    pass


_PREPARE_DYNAMIC_CARD_JS = """(el) => {
  const clickExpand = (root) => {
    root.querySelectorAll('span, div, button, a').forEach((node) => {
      const text = (node.textContent || '').trim();
      if (text === '展开' || text === '查看全文' || text === '全文') {
        node.click();
      }
    });
  };
  clickExpand(el);

  const unclip = (node) => {
    if (!(node instanceof HTMLElement)) return;
    node.style.overflow = 'visible';
    node.style.maxHeight = 'none';
    node.style.height = 'auto';
  };
  unclip(el);
  el.querySelectorAll(
    '__UNCLIP_SELECTORS__'
  ).forEach(unclip);

  el.querySelectorAll('img').forEach((img) => {
    const lazySrc =
      img.getAttribute('data-src') ||
      img.getAttribute('data-original') ||
      img.getAttribute('lazy-src');
    if (lazySrc && (!img.src || img.src.startsWith('data:'))) {
      img.src = lazySrc;
    }
  });
}"""

_PREPARE_DYNAMIC_CARD_JS = _PREPARE_DYNAMIC_CARD_JS.replace(
    "__UNCLIP_SELECTORS__", DYNAMIC_UNCLIP_SELECTORS
)

_LOAD_LAZY_IMAGES_JS = """async (el) => {
  const imgs = Array.from(el.querySelectorAll('img'));
  for (const img of imgs) {
    img.scrollIntoView({ block: 'center', behavior: 'instant' });
    await new Promise((resolve) => setTimeout(resolve, 120));
  }
  await Promise.all(
    imgs.map(
      (img) =>
        new Promise((resolve) => {
          if (img.complete && img.naturalHeight > 0) {
            resolve(true);
            return;
          }
          const done = () => resolve(true);
          img.addEventListener('load', done, { once: true });
          img.addEventListener('error', done, { once: true });
          setTimeout(done, 2500);
        })
    )
  );
  window.scrollTo(0, 0);
}"""

_MEASURE_ELEMENT_JS = """(el) => {
  const rect = el.getBoundingClientRect();
  return {
    x: rect.x + window.scrollX,
    y: rect.y + window.scrollY,
    width: Math.ceil(Math.max(rect.width, el.offsetWidth, el.scrollWidth)),
    height: Math.ceil(Math.max(rect.height, el.offsetHeight, el.scrollHeight)),
  };
}"""

MAX_DYNAMIC_SCREENSHOT_HEIGHT = 20000


def _parse_cookie_string(cookie_str: str) -> list:
    """将Cookie字符串解析为Playwright所需的Cookie列表"""
    cookies = []
    for item in cookie_str.split("; "):
        if "=" in item:
            name, value = item.split("=", 1)
            cookies.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".bilibili.com",
                    "path": "/",
                }
            )
    return cookies


async def init_browser(proxy=None, **kwargs) -> BrowserContext:
    """初始化浏览器 - 最佳实践配置"""
    logger.info("初始化Playwright浏览器")

    playwright = await async_playwright().start()

    # 优化的浏览器启动参数
    browser_args = [
        "--no-sandbox",  # 禁用沙盒（Docker环境必需）
        "--disable-setuid-sandbox",  # 禁用setuid沙盒
        "--disable-dev-shm-usage",  # 禁用/dev/shm使用
        "--disable-accelerated-2d-canvas",  # 禁用硬件加速画布
        "--no-first-run",  # 跳过首次运行设置
        "--no-zygote",  # 禁用zygote进程
        "--disable-gpu",  # 禁用GPU硬件加速
        "--disable-web-security",  # 禁用同源策略（如果需要）
        "--disable-features=VizDisplayCompositor",  # 禁用显示合成器
        #'--disable-extensions',            # 禁用扩展
        #'--disable-plugins',               # 禁用插件
        #'--disable-images',                # 不加载图片（可选，加快加载）
        #'--disable-javascript',            # 不执行JS（但我们需要JS，所以不加）
        "--disable-background-timer-throttling",  # 禁用后台定时器限制
        "--disable-backgrounding-occluded-windows",  # 禁用后台窗口限制
        "--disable-renderer-backgrounding",  # 禁用渲染器后台化
    ]

    browser = await playwright.chromium.launch(
        headless=True,
        args=browser_args,
        proxy={"server": proxy} if proxy else None,
        # 内存和性能优化
        handle_sigint=False,
        handle_sigterm=False,
        handle_sighup=False,
        **kwargs,
    )

    # 创建优化的浏览器上下文 - 高质量截图配置
    context = await browser.new_context(
        # 高分辨率视口设置
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        # 高质量渲染设置
        ignore_https_errors=True,  # 忽略HTTPS错误
        bypass_csp=True,  # 绕过内容安全策略
        # 禁用不必要的资源加载以提高性能
        permissions=[],  # 不授予任何权限
        # 高质量渲染选项
        device_scale_factor=2,  # 默认2倍缩放，提高清晰度
        is_mobile=False,  # PC模式
        has_touch=False,  # 非触摸设备
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

    async def _find_dynamic_card(self, page: Page) -> Optional[ElementHandle]:
        for selector in DYNAMIC_CARD_SELECTORS:
            try:
                card = await page.query_selector(selector)
                if card:
                    return card
            except Exception:
                continue
        return None

    async def _is_login_interstitial(self, page: Page) -> bool:
        return await page.evaluate(
            """() => {
                if (document.querySelector('.bili-opus-view, .bili-dyn-item, .opus-detail')) {
                    return false;
                }
                const text = document.body?.innerText || '';
                return text.includes('扫码登录') && text.includes('密码登录');
            }"""
        )

    async def _wait_for_dynamic_content(self, page: Page) -> bool:
        for selector in DYNAMIC_CONTENT_WAIT_SELECTORS:
            try:
                await page.wait_for_selector(selector, state="visible", timeout=8000)
                logger.debug(f"找到动态内容元素: {selector}")
                return True
            except Exception:
                continue
        return False

    async def _navigate_dynamic_page(
        self, page: Page, dynamic_id: int
    ) -> ElementHandle:
        urls = [
            f"https://www.bilibili.com/opus/{dynamic_id}",
            f"https://t.bilibili.com/{dynamic_id}",
        ]
        last_error: Optional[Exception] = None

        for url in urls:
            try:
                logger.debug(f"正在加载页面: {url}")
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=20000
                )
                if not response or response.status == 404:
                    continue

                current_url = page.url
                if "404" in current_url:
                    continue

                await page.wait_for_load_state(state="domcontentloaded", timeout=10000)
                await self._wait_for_dynamic_content(page)
                card = await self._find_dynamic_card(page)
                if card and not await self._is_login_interstitial(page):
                    logger.info(f"动态 {dynamic_id} 页面已加载: {current_url}")
                    try:
                        await page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception as e:
                        logger.warning(f"等待网络空闲超时: {e}")
                    await page.wait_for_timeout(500)
                    return card

                if await self._is_login_interstitial(page):
                    logger.debug(f"页面需要登录，尝试下一个 URL: {url}")
            except Notfound:
                raise
            except Exception as e:
                last_error = e
                logger.debug(f"加载页面失败 {url}: {e}")

        if last_error:
            raise last_error
        raise Notfound("动态不存在")

    async def _prepare_dynamic_card(self, page: Page, card) -> None:
        """展开长文本并解除高度限制，尽量让卡片完整渲染。"""
        await card.evaluate(_PREPARE_DYNAMIC_CARD_JS)
        await page.wait_for_timeout(300)
        await card.evaluate(_PREPARE_DYNAMIC_CARD_JS)
        await page.evaluate(_LOAD_LAZY_IMAGES_JS, card)
        await page.wait_for_timeout(300)
        await card.evaluate(_PREPARE_DYNAMIC_CARD_JS)

    async def _fit_viewport_for_element(self, page: Page, card) -> None:
        """将视口扩大到能容纳整张卡片，避免元素超出默认视口高度。"""
        box = await card.evaluate(_MEASURE_ELEMENT_JS)
        width = max(800, int(box["width"]) + 40)
        height = min(
            MAX_DYNAMIC_SCREENSHOT_HEIGHT,
            max(1080, int(box["y"]) + int(box["height"]) + 80),
        )
        await page.set_viewport_size({"width": width, "height": height})
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(200)

    async def _capture_dynamic_card(self, page: Page, card, dynamic_id: int) -> bytes:
        await self._prepare_dynamic_card(page, card)
        await self._fit_viewport_for_element(page, card)
        await self._prepare_dynamic_card(page, card)

        box = await card.evaluate(_MEASURE_ELEMENT_JS)
        logger.debug(f"动态 {dynamic_id} 内容区域大小: {box['width']}x{box['height']}")

        if box["height"] > MAX_DYNAMIC_SCREENSHOT_HEIGHT:
            logger.warning(
                f"动态 {dynamic_id} 内容过高 ({box['height']}px)，"
                f"截图高度限制为 {MAX_DYNAMIC_SCREENSHOT_HEIGHT}px"
            )

        screenshot = await card.screenshot(type="png")
        if not screenshot:
            raise Exception("截图结果为空")
        return screenshot

    async def get_dynamic_screenshot_pc(self, dynamic_id: int, page: Page):
        """加载动态/opus 页面并定位截图区域。"""
        logger.info(f"开始截图动态 {dynamic_id}")

        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            page.set_default_timeout(30000)

            card = await self._navigate_dynamic_page(page, dynamic_id)
            return page, card

        except Notfound:
            raise
        except Exception as e:
            logger.error(f"动态{dynamic_id}截图处理失败: {str(e)}")
            raise

    async def get_dynamic_screenshot(
        self, dynamic_id: int, timeout: int = 30000
    ) -> Tuple[Optional[bytes], Optional[str]]:
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
                page, card = await self.get_dynamic_screenshot_pc(dynamic_id, page)
                screenshot = await self._capture_dynamic_card(page, card, dynamic_id)
                screenshot_size = len(screenshot)
                logger.info(
                    f"动态 {dynamic_id} 截图成功，大小: {screenshot_size} bytes"
                )

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


async def get_dynamic_screenshot(
    dynamic_id: int,
) -> Tuple[Optional[bytes], Optional[str]]:
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
