"""Bridge to OneBot for group list and messaging."""

from __future__ import annotations

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
