"""Bridge to OneBot for group list and messaging."""

from __future__ import annotations

import asyncio
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
                groups.append({
                    "group_id": str(item.get("group_id", "")),
                    "group_name": item.get("group_name"),
                    "member_count": item.get("member_count"),
                })
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


async def _load_group_members(bot, group_id: str, self_ids: set[str]) -> dict[str, dict]:
    members: dict[str, dict] = {}
    api_gid = int(group_id) if group_id.isdigit() else group_id
    try:
        result = await bot.call_api("get_group_member_list", group_id=api_gid)
    except Exception as exc:
        logger.debug(f"get_group_member_list failed for {group_id} on {bot.self_id}: {exc}")
        return members

    for item in result:
        uid = str(item.get("user_id", "")).strip()
        nickname = item.get("card") or item.get("nickname")
        if not uid or uid in self_ids:
            continue
        label = (str(nickname).strip() if nickname else "") or None
        members[uid] = {"user_id": uid, "nickname": label}
    return members


async def _load_group_members_for_group(
    bots: list,
    group_id: str,
    self_ids: set[str],
) -> dict[str, dict]:
    for bot in bots:
        members = await _load_group_members(bot, group_id, self_ids)
        if members:
            return members
    return {}


async def get_user_list(group_ids: list[str] | None = None) -> List[dict]:
    """Fetch QQ users from friend list and optional group member lists."""
    users: dict[str, dict] = {}
    bots = get_bots()
    if not bots:
        logger.warning("No OneBot bots connected for user list")
        return []

    bot_list = list(bots.values())
    self_ids = {str(bot.self_id) for bot in bot_list}

    for bot in bot_list:
        try:
            result = await bot.call_api("get_friend_list")
            for item in result:
                nickname = item.get("remark") or item.get("nickname")
                _merge_user(users, str(item.get("user_id", "")), nickname, self_ids=self_ids)
        except Exception as exc:
            logger.error(f"Failed to get friend list from bot {bot.self_id}: {exc}")

    normalized_group_ids = [str(gid).strip() for gid in (group_ids or []) if str(gid).strip()]
    if normalized_group_ids and bot_list:
        member_chunks = await asyncio.gather(
            *[
                _load_group_members_for_group(bot_list, gid, self_ids)
                for gid in normalized_group_ids
            ]
        )
        for chunk in member_chunks:
            for uid, data in chunk.items():
                _merge_user(users, uid, data.get("nickname"), self_ids=self_ids)

    return sorted(users.values(), key=lambda item: item["user_id"])
