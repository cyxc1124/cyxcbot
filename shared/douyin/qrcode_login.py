"""Douyin web QR login via Playwright (flow adapted from douyin_parse).

Unlike Bilibili TV login (pure HTTP passport API), Douyin has no stable
public QR auth API here. We open www.douyin.com headless, trigger the
official scan-login panel, screenshot the QR image, then poll browser
cookies for ``sessionid``.
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from nonebot.log import logger

try:
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright
except Exception:  # pragma: no cover - optional at import time
    Browser = Any  # type: ignore[misc, assignment]
    BrowserContext = Any  # type: ignore[misc, assignment]
    Page = Any  # type: ignore[misc, assignment]
    async_playwright = None  # type: ignore[assignment]

DOUYIN_HOME = "https://www.douyin.com/"
DOUYIN_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

# 2026-08 实测抖音登录弹窗：容器 .XI37I0dP > img.RhjdbXj8[aria-label=二维码]
# （data:image/png；中心带抖音 logo）。哈希 class 可能再变，故保留语义/旧选择器兜底。
QR_SELECTORS = (
    ".XI37I0dP img",
    "img.RhjdbXj8",
    ".XI37I0dP",
    "img[aria-label*='二维码']",
    ".qrcode-img img",
    "img[src^='data:image/png;base64']",
    "img[src*='qrcode']",
    "img[src*='qr']",
    "img[alt*='二维码']",
    "[class*=qrcode] img",
)

_SESSION_TTL_SECONDS = 180
_QR_WAIT_SECONDS = 35
_POLL_DEFAULT_SECONDS = 120


class DouyinQrcodeError(Exception):
    """QR login failed."""


@dataclass
class DouyinQrSession:
    session_id: str
    image_base64: str
    playwright: Any
    browser: Any
    context: Any
    page: Any
    created_at: float = field(default_factory=time.monotonic)
    closed: bool = False


_sessions: dict[str, DouyinQrSession] = {}
_lock = asyncio.Lock()


def cookies_to_header(cookies: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def has_valid_login_cookie(cookies: list[dict[str, Any]]) -> bool:
    return any(
        cookie.get("name") == "sessionid" and cookie.get("value") for cookie in cookies
    )


def is_logged_in_url(url: str) -> bool:
    lower = (url or "").lower()
    if "douyin.com" not in lower:
        return False
    return not any(token in lower for token in ("passport", "/login", "/auth"))


def _clear_proxy_env() -> dict[str, str]:
    """Temporarily clear proxy env for Playwright; return removed pairs."""
    removed: dict[str, str] = {}
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "SOCKS_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "socks_proxy",
    ):
        if key in os.environ:
            removed[key] = os.environ.pop(key)
    return removed


def _restore_proxy_env(removed: dict[str, str]) -> None:
    os.environ.update(removed)


async def _open_login_panel(page: Page) -> None:
    clicked = False
    for fn in (
        lambda: page.click("#login-panel-new", timeout=3000),
        lambda: page.locator("[id*='login-panel'], [id*='login-pannel']").first.click(
            timeout=2000
        ),
        lambda: page.get_by_role("button", name="登录").first.click(timeout=2000),
    ):
        try:
            await fn()
            clicked = True
            break
        except Exception:
            continue
    if clicked:
        await page.wait_for_timeout(1500)

    for text in ("扫码登录", "二维码登录", "二维码"):
        try:
            await page.get_by_text(text, exact=False).first.click(timeout=1500)
            await page.wait_for_timeout(800)
            return
        except Exception:
            continue


async def _prefer_qr_img(element) -> object:
    """If the hit is the hashed wrapper, prefer the inner QR <img>."""
    try:
        tag = await element.evaluate("el => el.tagName")
    except Exception:
        return element
    if tag != "DIV":
        return element
    try:
        inner = await element.query_selector(
            "img[aria-label*='二维码'], img.RhjdbXj8, img[src^='data:image/png']"
        )
        if not inner:
            return element
        box = await inner.bounding_box()
        if box and box.get("width", 0) >= 100 and box.get("height", 0) >= 100:
            return inner
    except Exception:
        pass
    return element


async def _find_qr_element(page: Page):
    scopes = [page, *page.frames]
    for scope in scopes:
        for selector in QR_SELECTORS:
            try:
                element = await scope.query_selector(selector)
                if not element:
                    continue
                box = await element.bounding_box()
                if box and box.get("width", 0) >= 100 and box.get("height", 0) >= 100:
                    return await _prefer_qr_img(element)
            except Exception:
                continue
    return None


async def _wait_for_qr_element(page: Page, *, timeout_sec: int = _QR_WAIT_SECONDS):
    deadline = time.monotonic() + timeout_sec
    opened = False
    last_open_retry = 0.0
    while time.monotonic() < deadline:
        element = await _find_qr_element(page)
        if element:
            return element
        now = time.monotonic()
        if not opened:
            await _open_login_panel(page)
            opened = True
            last_open_retry = now
        elif now - last_open_retry >= 8:
            await _open_login_panel(page)
            last_open_retry = now
        await page.wait_for_timeout(500)
    return None


async def _extract_login_cookies(context: BrowserContext, page: Page) -> str | None:
    cookies = await context.cookies()
    if has_valid_login_cookie(cookies):
        return cookies_to_header(cookies)

    try:
        await page.goto(DOUYIN_HOME, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)
    except Exception:
        pass

    cookies = await context.cookies()
    if has_valid_login_cookie(cookies):
        return cookies_to_header(cookies)
    return None


async def close_qr_session(session_id: str) -> None:
    async with _lock:
        session = _sessions.pop(session_id, None)
    if session is None:
        return
    await _close_session(session)


async def _close_session(session: DouyinQrSession) -> None:
    if session.closed:
        return
    session.closed = True
    for closer in (
        getattr(session.browser, "close", None),
        getattr(session.playwright, "stop", None),
    ):
        if closer is None:
            continue
        try:
            await closer()
        except Exception:
            logger.opt(exception=True).debug("关闭抖音扫码会话失败")


async def _cleanup_stale_sessions_locked() -> None:
    now = time.monotonic()
    stale = [
        sid
        for sid, session in _sessions.items()
        if now - session.created_at > _SESSION_TTL_SECONDS
    ]
    for sid in stale:
        session = _sessions.pop(sid, None)
        if session is not None:
            await _close_session(session)


async def start_qrcode_login() -> dict[str, str]:
    """Launch headless Chromium, capture Douyin login QR.

    Returns ``{"session_id", "image_base64"}``.
    """
    if async_playwright is None:
        raise DouyinQrcodeError(
            "未安装 Playwright，请执行: pip install playwright && playwright install chromium"
        )

    removed_proxy = _clear_proxy_env()
    playwright = None
    browser: Optional[Browser] = None
    try:
        async with _lock:
            await _cleanup_stale_sessions_locked()
            # 同时只保留一个扫码会话，避免堆积 Chromium
            for sid in list(_sessions):
                old = _sessions.pop(sid)
                await _close_session(old)

        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            handle_sigint=False,
            handle_sigterm=False,
            handle_sighup=False,
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=DOUYIN_UA,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()
        await page.goto(DOUYIN_HOME, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)

        element = await _wait_for_qr_element(page)
        if element is None:
            raise DouyinQrcodeError("未找到二维码，请确认网络正常且页面未被拦截")

        png = await element.screenshot()
        image_base64 = base64.b64encode(png).decode("ascii")
        session_id = uuid.uuid4().hex
        session = DouyinQrSession(
            session_id=session_id,
            image_base64=image_base64,
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
        )
        async with _lock:
            _sessions[session_id] = session
        playwright = None
        browser = None
        logger.info("抖音扫码会话已创建 session_id={}", session_id[:8])
        return {"session_id": session_id, "image_base64": image_base64}
    except DouyinQrcodeError:
        if browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()
        raise
    except Exception as exc:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass
        logger.opt(exception=True).error("抖音扫码启动失败")
        msg = str(exc)
        if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
            raise DouyinQrcodeError(
                "未安装 Playwright 浏览器，请在项目环境执行: "
                "./.venv/bin/playwright install chromium"
            ) from exc
        raise DouyinQrcodeError(f"获取二维码失败: {exc}") from exc
    finally:
        _restore_proxy_env(removed_proxy)


async def poll_qrcode_login(
    session_id: str,
    *,
    timeout_seconds: int = _POLL_DEFAULT_SECONDS,
) -> str:
    """Poll until Douyin App confirms login. Returns cookie header string."""
    sid = (session_id or "").strip()
    if not sid:
        raise DouyinQrcodeError("缺少 session_id，请重新获取二维码")

    async with _lock:
        session = _sessions.get(sid)
    if session is None:
        raise DouyinQrcodeError("二维码会话不存在或已过期，请重新获取")

    if session.closed or session.page is None or session.context is None:
        await close_qr_session(sid)
        raise DouyinQrcodeError("二维码会话已关闭，请重新获取")

    page = session.page
    context = session.context
    start_url = page.url

    try:
        for i in range(max(1, int(timeout_seconds))):
            cookies = await context.cookies()
            if has_valid_login_cookie(cookies):
                cookie_header = await _extract_login_cookies(context, page)
                if cookie_header:
                    return cookie_header

            current_url = page.url
            if is_logged_in_url(current_url) and current_url != start_url:
                cookie_header = await _extract_login_cookies(context, page)
                if cookie_header:
                    return cookie_header

            try:
                text = await page.inner_text("body")
                if any(k in text for k in ("登录成功", "已登录", "登录完成")):
                    cookie_header = await _extract_login_cookies(context, page)
                    if cookie_header:
                        return cookie_header
            except Exception:
                pass

            if i % 15 == 0:
                logger.debug("抖音扫码等待中 session={} tick={}", sid[:8], i)
            await asyncio.sleep(1)

        raise DouyinQrcodeError("二维码已超时，请重新获取（扫码后需在手机上确认）")
    finally:
        await close_qr_session(sid)
