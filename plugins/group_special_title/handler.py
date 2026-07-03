"""Handle group special title set commands."""

from __future__ import annotations

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.log import logger

from shared.group_special_title import (
    DAILY_USAGE_LIMIT,
    parse_title_command,
    validate_title,
)

from .usage_store import get_today_usage, record_successful_set


async def handle_group_special_title(bot: Bot, event: GroupMessageEvent) -> str | None:
    """Apply title when message is a title command; return reply text or None."""
    title = parse_title_command(event.get_plaintext())
    if title is None:
        return None

    error = validate_title(title)
    if error:
        return error

    group_id = str(event.group_id)
    user_id = str(event.user_id)

    used = await get_today_usage(group_id, user_id)
    if used >= DAILY_USAGE_LIMIT:
        return f"今日已设置 {DAILY_USAGE_LIMIT} 次，请明天再试"

    try:
        await bot.set_group_special_title(
            group_id=event.group_id,
            user_id=event.user_id,
            special_title=title,
            duration=-1,
        )
    except ActionFailed as exc:
        logger.warning(
            "设置群头衔失败: group={} user={} title={} err={}",
            group_id,
            user_id,
            title,
            exc,
        )
        return "设置头衔失败，请确认机器人有「设置专属头衔」权限"

    new_count = await record_successful_set(group_id, user_id)
    left = DAILY_USAGE_LIMIT - new_count
    if left > 0:
        return f"已设置头衔「{title}」，今日还可设置 {left} 次"
    return f"已设置头衔「{title}」，今日次数已用完"
