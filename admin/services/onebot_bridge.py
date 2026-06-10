"""Bridge to OneBot for group list and messaging."""

from __future__ import annotations

import time
from typing import List

from nonebot import get_bots
from nonebot.log import logger


async def get_group_list() -> List[dict]:
    """Fetch group list from connected OneBot bots."""
    groups: List[dict] = []
    bots = get_bots()
    if not bots:
        logger.warning("No OneBot bots connected for group list")
        return groups

    for bot in bots.values():
        try:
            result = await bot.call_api("get_group_list")
            for item in result:
                groups.append(
                    {
                        "group_id": str(item.get("group_id", "")),
                        "group_name": item.get("group_name"),
                        "member_count": item.get("member_count"),
                    }
                )
        except Exception as exc:
            logger.error(f"Failed to get group list from bot {bot.self_id}: {exc}")

    # Deduplicate by group_id
    seen = set()
    unique = []
    for g in groups:
        gid = g["group_id"]
        if gid and gid not in seen:
            seen.add(gid)
            unique.append(g)
    return unique


def _merge_user(
    users: dict[str, dict],
    user_id: str,
    nickname: str | None,
    *,
    self_ids: set[str],
) -> None:
    uid = str(user_id).strip()
    if not uid or uid in self_ids:
        return
    label = (nickname or "").strip() or None
    if uid in users:
        if label and not users[uid].get("nickname"):
            users[uid]["nickname"] = label
        return
    users[uid] = {"user_id": uid, "nickname": label}


_FRIEND_LIST_CACHE: tuple[float, list[dict]] | None = None
_FRIEND_LIST_CACHE_TTL_SECONDS = 120


def invalidate_user_list_cache() -> None:
    global _FRIEND_LIST_CACHE
    _FRIEND_LIST_CACHE = None


async def get_friend_list() -> List[dict]:
    """Fetch QQ users from the bot friend list only."""
    global _FRIEND_LIST_CACHE
    now = time.time()
    if (
        _FRIEND_LIST_CACHE is not None
        and now - _FRIEND_LIST_CACHE[0] < _FRIEND_LIST_CACHE_TTL_SECONDS
    ):
        return [dict(user) for user in _FRIEND_LIST_CACHE[1]]

    users: dict[str, dict] = {}
    bots = get_bots()
    if not bots:
        logger.warning("No OneBot bots connected for friend list")
        return []

    bot_list = list(bots.values())
    self_ids = {str(bot.self_id) for bot in bot_list}

    for bot in bot_list:
        try:
            result = await bot.call_api("get_friend_list")
            for item in result:
                nickname = item.get("remark") or item.get("nickname")
                _merge_user(
                    users, str(item.get("user_id", "")), nickname, self_ids=self_ids
                )
        except Exception as exc:
            logger.error(f"Failed to get friend list from bot {bot.self_id}: {exc}")

    result = sorted(users.values(), key=lambda item: item["user_id"])
    _FRIEND_LIST_CACHE = (now, result)
    return [dict(user) for user in result]


async def get_user_list() -> List[dict]:
    """Backward-compatible alias for friend list."""
    return await get_friend_list()
