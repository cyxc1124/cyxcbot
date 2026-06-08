"""Bilibili and QQ (OneBot) connection status."""

from __future__ import annotations

from typing import Any, Dict, List

import aiohttp
from nonebot import get_bots
from nonebot.log import logger

from shared.config.service import get_config_service

_NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
_NAV_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}


async def get_bilibili_connection_status() -> Dict[str, Any]:
    snap = get_config_service().get_snapshot()
    configured = snap.bilibili_cookie_set

    if not configured or not snap.bilibili_cookie:
        return {
            "configured": False,
            "logged_in": False,
            "username": None,
            "uid": None,
            "message": "未配置 Cookie，请在系统设置中填写",
        }

    try:
        headers = {**_NAV_HEADERS, "Cookie": snap.bilibili_cookie}
        async with aiohttp.ClientSession() as session:
            async with session.get(_NAV_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return {
                        "configured": True,
                        "logged_in": False,
                        "username": None,
                        "uid": None,
                        "message": f"验证失败（HTTP {resp.status}）",
                    }
                data = await resp.json()

        if data.get("code") != 0:
            return {
                "configured": True,
                "logged_in": False,
                "username": None,
                "uid": None,
                "message": data.get("message") or "Cookie 无效或已过期",
            }

        nav = data.get("data") or {}
        if not nav.get("isLogin"):
            return {
                "configured": True,
                "logged_in": False,
                "username": None,
                "uid": None,
                "message": "Cookie 未登录或已失效",
            }

        username = nav.get("uname")
        mid = nav.get("mid")
        return {
            "configured": True,
            "logged_in": True,
            "username": username,
            "uid": str(mid) if mid is not None else None,
            "message": f"已登录 · UID {mid}" if mid else "已登录",
        }
    except Exception as exc:
        logger.warning(f"Bilibili login check failed: {exc}")
        return {
            "configured": True,
            "logged_in": False,
            "username": None,
            "uid": None,
            "message": "无法验证登录状态",
        }


async def get_qq_connection_status() -> Dict[str, Any]:
    bots = get_bots()
    if not bots:
        return {
            "connected": False,
            "bot_count": 0,
            "bots": [],
            "message": "未连接 OneBot，请检查 QQ 协议端",
        }

    bot_infos: List[Dict[str, Any]] = []
    for self_id, bot in bots.items():
        qq = str(self_id)
        nickname: str | None = None
        try:
            info = await bot.call_api("get_login_info")
            qq = str(info.get("user_id", self_id))
            nickname = info.get("nickname")
        except Exception as exc:
            logger.debug(f"get_login_info failed for {self_id}: {exc}")

        bot_infos.append({"qq": qq, "nickname": nickname})

    if len(bot_infos) == 1:
        bot = bot_infos[0]
        label = bot["nickname"] or bot["qq"]
        message = f"QQ {bot['qq']}（{label}）"
    else:
        message = f"已连接 {len(bot_infos)} 个 QQ 账号"

    return {
        "connected": True,
        "bot_count": len(bot_infos),
        "bots": bot_infos,
        "message": message,
    }


async def get_connections_status() -> Dict[str, Any]:
    bilibili = await get_bilibili_connection_status()
    qq = await get_qq_connection_status()
    return {"bilibili": bilibili, "qq": qq}
