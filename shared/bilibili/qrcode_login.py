"""Bilibili TV QR code login (same flow as biliup)."""

from __future__ import annotations

import asyncio
import hashlib
import time
import urllib.parse
from typing import Any

import aiohttp

_BILI_TV_APPKEY = "4409e2ce8ffd12b8"
_BILI_TV_APPSEC = "59b43e04ad6965f34319062b478f83dd"

_AUTH_CODE_URL = "https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
_POLL_URL = "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"

_POLL_WAITING_CODE = 86039

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 BiliApp"
    ),
    "Referer": "https://www.bilibili.com/",
}


class BilibiliQrcodeError(Exception):
    """QR login failed."""


def _sign_params(params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode(params)
    return hashlib.md5(f"{query}{_BILI_TV_APPSEC}".encode()).hexdigest()


def _signed_tv_params(*, auth_code: str | None = None) -> dict[str, Any]:
    """Build signed params; key order must match biliup for correct sign."""
    ts = int(time.time())
    if auth_code:
        params: dict[str, Any] = {
            "appkey": _BILI_TV_APPKEY,
            "auth_code": auth_code,
            "local_id": "0",
            "ts": ts,
        }
    else:
        params = {
            "appkey": _BILI_TV_APPKEY,
            "local_id": "0",
            "ts": ts,
        }
    params["sign"] = _sign_params(params)
    return params


def cookie_info_to_header(cookie_info: dict[str, Any]) -> str:
    cookies = cookie_info.get("cookies") or []
    pairs = [
        f"{item['name']}={item['value']}"
        for item in cookies
        if isinstance(item, dict) and item.get("name") and "value" in item
    ]
    if not pairs:
        raise BilibiliQrcodeError("登录响应中未包含 Cookie")
    return "; ".join(pairs)


async def get_tv_qrcode() -> dict[str, Any]:
    """Request a TV login QR code. Returns the raw Bilibili API JSON."""
    params = _signed_tv_params()
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout, headers=_DEFAULT_HEADERS) as session:
        async with session.post(_AUTH_CODE_URL, data=params) as resp:
            payload = await resp.json(content_type=None)

    if not payload or payload.get("code") != 0:
        message = (payload or {}).get("message") or "获取二维码失败"
        raise BilibiliQrcodeError(message)

    data = payload.get("data") or {}
    if not data.get("url") or not data.get("auth_code"):
        raise BilibiliQrcodeError("二维码响应格式异常")

    return payload


async def poll_tv_qrcode_login(
    qrcode_payload: dict[str, Any],
    *,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Poll until the QR code is scanned or timeout. Returns login `data` dict."""
    auth_code = (qrcode_payload.get("data") or {}).get("auth_code")
    if not auth_code:
        raise BilibiliQrcodeError("缺少 auth_code，请重新获取二维码")

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout, headers=_DEFAULT_HEADERS) as session:
        for _ in range(timeout_seconds):
            params = _signed_tv_params(auth_code=auth_code)
            async with session.post(_POLL_URL, data=params) as resp:
                payload = await resp.json(content_type=None)

            if not payload:
                raise BilibiliQrcodeError("轮询登录状态失败")

            code = payload.get("code")
            if code == 0:
                data = payload.get("data") or {}
                if not data.get("cookie_info"):
                    raise BilibiliQrcodeError("登录成功但未返回 Cookie")
                return data

            if code == _POLL_WAITING_CODE:
                await asyncio.sleep(1)
                continue

            message = payload.get("message") or f"扫码登录失败（code={code}）"
            raise BilibiliQrcodeError(message)

    raise BilibiliQrcodeError("二维码已超时，请重新获取")
