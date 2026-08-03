"""Douyin cookie validation (ported from douyin-downloader CookieManager)."""

from __future__ import annotations

from nonebot.log import logger

from .cookie_utils import parse_cookie_header, sanitize_cookies

REQUIRED_COOKIE_KEYS = frozenset({"ttwid", "odin_tt", "passport_csrf_token"})


def validate_cookies(cookies: dict[str, str]) -> bool:
    """Return True when required session cookies are present.

    ``msToken`` may be missing; it is generated on demand.
    """
    clean = sanitize_cookies(cookies or {})
    missing = [key for key in sorted(REQUIRED_COOKIE_KEYS) if not clean.get(key)]
    if missing:
        logger.warning("抖音 Cookie 校验失败，缺少: {}", ", ".join(missing))
        return False
    if not clean.get("msToken"):
        logger.info("抖音 Cookie 未含 msToken，将在请求时自动生成")
    return True


def validate_cookie_header(cookie_header: str) -> bool:
    return validate_cookies(parse_cookie_header(cookie_header or ""))


def cookies_from_header(cookie_header: str) -> dict[str, str]:
    return sanitize_cookies(parse_cookie_header(cookie_header or ""))
