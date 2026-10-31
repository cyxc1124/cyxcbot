"""B 站链接解析：视频发送与封面降级。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11.message import Message
from nonebot.log import logger

from shared.adapter.bots import is_official_qq_bot
from shared.adapter.inbound import user_id_of
from shared.adapter.outbound import (
    OfficialReplyLimitError,
    official_reply_remaining,
    send_event_message,
)
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.message_templates import LinkMessageTemplates
from utils.bilibili_api import VideoInfo

from .send_result import is_onebot_send_success
from .sender import build_video_link_message, official_reply_message, reply_batches


def all_sends_ok(send_results: list[object] | None) -> bool:
    return bool(send_results) and all(
        is_onebot_send_success(item) for item in send_results
    )


def any_send_ok(send_results: list[object] | None) -> bool:
    return bool(send_results) and any(
        is_onebot_send_success(item) for item in send_results
    )


async def send_batches(bot: Any, event: Any, batches: list[Message]) -> list[object]:
    if is_official_qq_bot(bot):
        message = Message([segment for batch in batches for segment in batch])
        reply = official_reply_message(message, official_reply_remaining(event))
        results: list[object] = []
        for segment in reply:
            try:
                results.append(await send_event_message(bot, event, Message([segment])))
            except OfficialReplyLimitError:
                raise
            except LoggedQQApiError as exc:
                if segment.type not in {"image", "video"} or exc.code not in {
                    50059,
                    22006,
                    304061,
                    304080,
                    40034004,
                    40034006,
                }:
                    raise
                results.append(None)
            except Exception:
                if segment.type not in {"image", "video"}:
                    raise
                logger.opt(exception=True).warning(
                    "B 站链接解析媒体发送失败 user={}，继续发送剩余结果",
                    user_id_of(event),
                )
                results.append(None)
        return results
    return [await send_event_message(bot, event, batch) for batch in batches]


async def send_video_with_cover_fallback(
    bot: Any,
    event: Any,
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
    if is_official_qq_bot(bot):
        # 视频、封面、文案分别发送；媒体拒绝后继续，避免重发已被接受的部分。
        return await send_batches(bot, event, [reply])
    send_results: list[object] | None = None
    try:
        send_results = await send_batches(bot, event, reply_batches(reply))
    except ActionFailed as exc:
        detail = str(
            getattr(exc, "wording", None) or getattr(exc, "message", None) or exc
        )
        logger.warning(
            "B 站链接解析视频发送失败 user={} retcode={} detail={!r}，降级为封面+文字",
            user_id_of(event),
            getattr(exc, "retcode", None),
            detail[:200],
        )
    except Exception:
        logger.opt(exception=True).warning(
            "B 站链接解析视频发送异常 user={}，降级为封面+文字", user_id_of(event)
        )

    if all_sends_ok(send_results):
        return send_results or []
    if any_send_ok(send_results):
        # 视频批可能已发出，避免再发一遍封面造成重复；交由上层记 warning
        return send_results or []

    cover = await asyncio.to_thread(build_video_link_message, video, templates)
    return await send_batches(bot, event, [cover])
