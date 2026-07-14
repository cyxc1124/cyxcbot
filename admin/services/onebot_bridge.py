"""Bridge to OneBot for group list and messaging."""

from __future__ import annotations

import time
from typing import List, Literal

from nonebot import get_bots
from nonebot.log import logger

OneBotListFetchStatus = Literal["ok", "offline", "incomplete"]
# Backward-compatible alias for friend-list callers/tests.
FriendListFetchStatus = OneBotListFetchStatus


async def get_group_list_with_status() -> tuple[List[dict], OneBotListFetchStatus]:
    """Return ``(groups, status)``.

    *status*:
    - ``ok``: every connected bot's ``get_group_list`` succeeded (may be empty)
    - ``offline``: no OneBot connected
    - ``incomplete``: at least one bot is connected but a fetch failed
    """
    groups: List[dict] = []
    bots = get_bots()
    if not bots:
        logger.warning("无已连接的 OneBot 机器人，无法获取群列表")
        return groups, "offline"

    success_count = 0
    for bot in bots.values():
        try:
            result = await bot.call_api("get_group_list")
            success_count += 1
            for item in result:
                groups.append(
                    {
                        "group_id": str(item.get("group_id", "")),
                        "group_name": item.get("group_name"),
                        "member_count": item.get("member_count"),
                    }
                )
        except Exception as exc:
            logger.error("从机器人 {} 获取群列表失败: {}", bot.self_id, exc)

    seen = set()
    unique = []
    for g in groups:
        gid = g["group_id"]
        if gid and gid not in seen:
            seen.add(gid)
            unique.append(g)

    if success_count == len(bots):
        return unique, "ok"
    return unique, "incomplete"


async def get_group_list_with_availability() -> tuple[List[dict], bool]:
    """Return ``(groups, available)``.

    *available* is true only when every connected bot's ``get_group_list`` succeeded.
    """
    groups, status = await get_group_list_with_status()
    return groups, status == "ok"


async def get_group_list() -> List[dict]:
    """Fetch group list from connected OneBot bots."""
    groups, _ = await get_group_list_with_status()
    return groups


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


# (timestamp, users, bot self_ids that produced the complete fetch)
_FRIEND_LIST_CACHE: tuple[float, list[dict], frozenset[str]] | None = None
_FRIEND_LIST_CACHE_TTL_SECONDS = 120


def invalidate_user_list_cache() -> None:
    global _FRIEND_LIST_CACHE
    _FRIEND_LIST_CACHE = None


async def get_friend_list_with_availability() -> tuple[
    List[dict], OneBotListFetchStatus
]:
    """Return ``(friends, status)``.

    *status*:
    - ``ok``: every connected bot's ``get_friend_list`` succeeded (may be empty)
    - ``offline``: no OneBot connected
    - ``incomplete``: at least one bot is connected but a fetch failed

    Incomplete results are not cached. Cached ``ok`` results are only reused when the
    live bot set still matches the bots that produced the cache entry.
    """
    global _FRIEND_LIST_CACHE
    now = time.time()
    bots = get_bots()
    live_bot_ids = frozenset(str(bot.self_id) for bot in bots.values())

    if (
        _FRIEND_LIST_CACHE is not None
        and now - _FRIEND_LIST_CACHE[0] < _FRIEND_LIST_CACHE_TTL_SECONDS
    ):
        _cached_ts, cached_users, cached_bot_ids = _FRIEND_LIST_CACHE
        if not bots:
            _FRIEND_LIST_CACHE = None
            logger.warning("无已连接的 OneBot 机器人，丢弃过期好友列表缓存")
            return [], "offline"
        if live_bot_ids == cached_bot_ids:
            return [dict(user) for user in cached_users], "ok"
        # Bot set changed within TTL — do not trust the previous complete snapshot.
        _FRIEND_LIST_CACHE = None

    users: dict[str, dict] = {}
    if not bots:
        logger.warning("无已连接的 OneBot 机器人，无法获取好友列表")
        return [], "offline"

    bot_list = list(bots.values())
    self_ids = set(live_bot_ids)
    success_count = 0

    for bot in bot_list:
        try:
            result = await bot.call_api("get_friend_list")
            success_count += 1
            for item in result:
                nickname = item.get("remark") or item.get("nickname")
                _merge_user(
                    users, str(item.get("user_id", "")), nickname, self_ids=self_ids
                )
        except Exception as exc:
            logger.error("从机器人 {} 获取好友列表失败: {}", bot.self_id, exc)

    result = sorted(users.values(), key=lambda item: item["user_id"])
    if success_count == len(bot_list):
        _FRIEND_LIST_CACHE = (now, result, live_bot_ids)
        return [dict(user) for user in result], "ok"

    logger.warning(
        "好友列表获取不完整 ({}/{})，跳过缓存",
        success_count,
        len(bot_list),
    )
    return [dict(user) for user in result], "incomplete"


async def get_friend_list() -> List[dict]:
    """Fetch QQ users from the bot friend list only."""
    users, _ = await get_friend_list_with_availability()
    return users


async def get_user_list() -> List[dict]:
    """Backward-compatible alias for friend list."""
    return await get_friend_list()
