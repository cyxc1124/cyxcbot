"""X 链接解析结果消息构建。"""

from __future__ import annotations

from typing import Iterable, List, Optional, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import XLinkMessageTemplates
from shared.notify.message_template import build_message_from_template
from utils.x_api import TweetItem

SegmentPart = Union[MessageSegment, str]

_MEDIA_SEG_TYPES = frozenset({"image"})
# QQ NT sendMsg 同条图片过多会 result=34；按批拆分。
MAX_MEDIA_PER_MESSAGE = 10


def build_x_link_message(
    tweet: TweetItem,
    templates: Optional[XLinkMessageTemplates] = None,
) -> Message:
    tpl = templates or XLinkMessageTemplates()
    text_variables = {
        "name": tweet.name or tweet.username,
        "username": tweet.username,
        "time": tweet.format_time(),
        "text": tweet.text or "",
        "url": tweet.url,
        "tweet_id": str(tweet.id),
    }

    def media_parts() -> Iterable[SegmentPart]:
        parts: List[SegmentPart] = []
        for image_url in tweet.media_urls:
            try:
                parts.append(MessageSegment.image(image_url))
            except Exception:
                logger.opt(exception=True).warning("添加推文图片失败: {}", image_url)
        return parts

    return build_message_from_template(
        tpl.tweet,
        text_variables,
        {"media": media_parts},
    )


def split_media_and_caption(message: Message) -> tuple[Message, Message]:
    """Split into (media, caption). Caption may be empty Message."""
    media = Message()
    caption = Message()
    for seg in message:
        if seg.type in _MEDIA_SEG_TYPES:
            media.append(seg)
        elif seg.type == "text" and not str(seg.data.get("text", "")).strip():
            continue
        else:
            caption.append(seg)
    return media, caption


def _chunk_media(media: Message, *, size: int = MAX_MEDIA_PER_MESSAGE) -> list[Message]:
    chunks: list[Message] = []
    current = Message()
    count = 0
    for seg in media:
        if count >= size:
            chunks.append(current)
            current = Message()
            count = 0
        current.append(seg)
        count += 1
    if current:
        chunks.append(current)
    return chunks


def reply_batches(message: Message) -> list[Message]:
    """Split for QQ limits: 同条图片过多会 sendMsg result=34。"""
    if not message:
        return []
    media, caption = split_media_and_caption(message)
    if not media:
        return [caption] if caption else []

    media_chunks = _chunk_media(media)

    # 少量纯图 + 文案可同条
    if (
        len(media_chunks) == 1
        and caption
        and len(media_chunks[0]) <= MAX_MEDIA_PER_MESSAGE
    ):
        combined = Message()
        for seg in media_chunks[0]:
            combined.append(seg)
        for seg in caption:
            combined.append(seg)
        return [combined]

    batches = list(media_chunks)
    if caption:
        batches.append(caption)
    return batches
