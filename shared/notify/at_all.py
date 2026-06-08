"""@全体成员 prefix helpers for group notifications."""

from __future__ import annotations

from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

LIVE_AT_ALL_FALLBACK = "📢 请关注直播动态！"
DYNAMIC_AT_ALL_FALLBACK = "📢 新动态提醒！"


async def bot_can_at_all(bot: Bot, group_id: str) -> bool:
    """Return whether the bot may @all in this group (requires admin/owner)."""
    try:
        bot_info = await bot.get_group_member_info(
            group_id=int(group_id),
            user_id=int(bot.self_id),
            no_cache=False,
        )
        role = bot_info.get("role", "member")
        return role in ("admin", "owner")
    except Exception:
        return False


async def resolve_at_all_prefix(
    bot: Bot,
    group_id: str,
    *,
    enabled: bool,
    fallback: str,
) -> Message:
    """Build @all segment or fallback text when @all is disabled or not allowed."""
    prefix = Message()
    if enabled and await bot_can_at_all(bot, group_id):
        prefix.append(MessageSegment.at("all"))
    else:
        prefix.append(fallback)
    prefix.append(" ")
    return prefix
