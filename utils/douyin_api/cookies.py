"""Douyin cookie validation (ported from douyin-downloader CookieManager)."""

from __future__ import annotations

from nonebot.log import logger

from .cookie_utils import parse_cookie_header, sanitize_cookies

REQUIRED_COOKIE_KEYS = frozenset({"ttwid", "odin_tt", "passport_csrf_token"})


def validate_cookies(cookies: dict[str, str]) -> bool:
    """Return True when recommended session cookies are present.

    对齐 douyin-downloader：缺键只表示「不完整」，调用方应 warning 后仍可尝试。
    ``msToken`` 可缺，运行时会自动生成。
    """
    clean = sanitize_cookies(cookies or {})
    missing = [key for key in sorted(REQUIRED_COOKIE_KEYS) if not clean.get(key)]
    if missing:
        logger.warning("抖音 Cookie 不完整，缺少: {}", ", ".join(missing))
        return False
    if not clean.get("msToken"):
        logger.info("抖音 Cookie 未含 msToken，将在请求时自动生成")
    return True


def validate_cookie_header(cookie_header: str) -> bool:
    return validate_cookies(parse_cookie_header(cookie_header or ""))


def cookies_from_header(cookie_header: str) -> dict[str, str]:
    return sanitize_cookies(parse_cookie_header(cookie_header or ""))
