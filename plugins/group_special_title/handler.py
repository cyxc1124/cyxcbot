"""Handle group special title set commands."""

from __future__ import annotations

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed, ApiNotAvailable
from nonebot.log import logger

from shared.config.service import get_config_service
from shared.group_special_title import parse_title_from_message, validate_title
from shared.group_special_title_policy import (
    daily_usage_limit_from_snapshot,
    is_group_special_title_enabled_from_snapshot,
)

from .usage_store import get_today_usage, record_successful_set


async def _bot_group_role(bot: Bot, group_id: int) -> str | None:
    try:
        info = await bot.get_group_member_info(
            group_id=group_id,
            user_id=int(bot.self_id),
            no_cache=True,
        )
    except (ActionFailed, ApiNotAvailable):
        logger.opt(exception=True).warning(
            "读取机器人群身份失败: group={} self={}",
            group_id,
            bot.self_id,
        )
        return None
    role = info.get("role")
    return role if isinstance(role, str) else None


async def handle_group_special_title(bot: Bot, event: GroupMessageEvent) -> None:
    """Apply title when message is a title command; never replies in group."""
    title = parse_title_from_message(event.message)
    if title is None:
        return

    group_id = str(event.group_id)
    user_id = str(event.user_id)
    snap = get_config_service().get_snapshot()
    if not is_group_special_title_enabled_from_snapshot(group_id, snap):
        return

    daily_limit = daily_usage_limit_from_snapshot(snap)
    logger.info(
        "处理群头衔命令: group={} user={} title={}",
        group_id,
        user_id,
        title,
    )

    error = validate_title(title)
    if error:
        logger.info(
            "群头衔命令无效: group={} user={} reason={}",
            group_id,
            user_id,
            error,
        )
        return

    used = await get_today_usage(group_id, user_id)
    if used >= daily_limit:
        logger.info(
            "群头衔今日次数已用尽: group={} user={} limit={}",
            group_id,
            user_id,
            daily_limit,
        )
        return

    bot_role = await _bot_group_role(bot, event.group_id)
    if bot_role != "owner":
        logger.warning(
            "机器人非群主，无法设置头衔: group={} role={}",
            group_id,
            bot_role,
        )
        return

    try:
        await bot.set_group_special_title(
            group_id=event.group_id,
            user_id=event.user_id,
            special_title=title,
        )
    except (ActionFailed, ApiNotAvailable) as exc:
        if isinstance(exc, ActionFailed):
            logger.warning(
                "设置群头衔 API 失败: group={} user={} title={} retcode={} msg={}",
                group_id,
                user_id,
                title,
                exc.retcode,
                exc.message,
            )
        else:
            logger.warning(
                "设置群头衔 API 不可用: group={} user={} title={}",
                group_id,
                user_id,
                title,
            )
        return

    await record_successful_set(group_id, user_id)
    logger.info(
        "群头衔已设置: group={} user={} title={}",
        group_id,
        user_id,
        title,
    )
