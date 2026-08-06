"""B 站链接解析：视频发送与封面降级。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11.message import Message
from nonebot.log import logger

from shared.config.message_templates import LinkMessageTemplates
from utils.bilibili_api import VideoInfo

from .send_result import is_onebot_send_success
from .sender import build_video_link_message, reply_batches


def all_sends_ok(send_results: list[object] | None) -> bool:
    return bool(send_results) and all(
        is_onebot_send_success(item) for item in send_results
    )


def any_send_ok(send_results: list[object] | None) -> bool:
    return bool(send_results) and any(
        is_onebot_send_success(item) for item in send_results
    )


async def send_batches(
    bot: Bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    batches: list[Message],
) -> list[object]:
    send_results: list[object] = []
    for batch in batches:
        if isinstance(event, GroupMessageEvent):
            send_results.append(
                await bot.send_group_msg(group_id=event.group_id, message=batch)
            )
        else:
            send_results.append(
                await bot.send_private_msg(user_id=event.user_id, message=batch)
            )
    return send_results


async def send_video_with_cover_fallback(
    bot: Bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    *,
    video: VideoInfo,
    video_path: Path,
    templates: LinkMessageTemplates,
) -> list[object]:
    """先发视频；整批失败（路径不可见等）时降级为仅封面+文字。"""
    reply = await asyncio.to_thread(
        build_video_link_message,
        video,
        templates,
        video_path=video_path,
    )
    send_results: list[object] | None = None
    try:
        send_results = await send_batches(bot, event, reply_batches(reply))
    except ActionFailed as exc:
        detail = str(
            getattr(exc, "wording", None) or getattr(exc, "message", None) or exc
        )
        logger.warning(
            "B 站链接解析视频发送失败 user={} retcode={} detail={!r}，降级为封面+文字",
            event.user_id,
            getattr(exc, "retcode", None),
            detail[:200],
        )
    except Exception:
        logger.opt(exception=True).warning(
            "B 站链接解析视频发送异常 user={}，降级为封面+文字", event.user_id
        )

    if all_sends_ok(send_results):
        return send_results or []
    if any_send_ok(send_results):
        # 视频批可能已发出，避免再发一遍封面造成重复；交由上层记 warning
        return send_results or []

    cover = await asyncio.to_thread(build_video_link_message, video, templates)
    return await send_batches(bot, event, [cover])
