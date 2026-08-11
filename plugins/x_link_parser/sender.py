"""X 链接解析结果消息构建。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import XLinkMessageTemplates
from shared.notify.message_template import build_message_from_template
from utils.x_api import TweetItem
from utils.x_api.models import TweetMediaItem

SegmentPart = Union[MessageSegment, str]

# QQ NT sendMsg 同条图片过多会 result=34；按批拆分。
MAX_MEDIA_PER_MESSAGE = 10


def _video_parts(file_path: Path) -> Iterable[SegmentPart]:
    if not file_path.exists():
        return []
    try:
        if file_path.stat().st_size <= 0:
            logger.warning("X 视频文件为空: {}", file_path)
            return []
        return [MessageSegment.video(file_path.resolve())]
    except Exception:
        logger.opt(exception=True).warning("添加 X 视频段失败: {}", file_path)
        return []


def _image_parts(file_path: Path) -> Iterable[SegmentPart]:
    if not file_path.exists():
        return []
    try:
        if file_path.stat().st_size <= 0:
            logger.warning("X 图片文件为空: {}", file_path)
            return []
        return [MessageSegment.image(file_path.resolve())]
    except Exception:
        logger.opt(exception=True).warning("添加推文图片失败: {}", file_path)
        return []


def _media_parts(tweet: TweetItem) -> Iterable[SegmentPart]:
    items: list[TweetMediaItem] = list(tweet.media_items or [])
    if not items and tweet.media_urls:
        items = [TweetMediaItem(kind="image", url=u) for u in tweet.media_urls]

    parts: List[SegmentPart] = []
    for item in items:
        if item.file_path is None:
            continue
        if item.kind == "video":
            parts.extend(_video_parts(item.file_path))
        else:
            parts.extend(_image_parts(item.file_path))
    return parts


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

    return build_message_from_template(
        tpl.tweet,
        text_variables,
        {"media": lambda: _media_parts(tweet)},
    )


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


def _text_image_batches(non_video: Message) -> list[Message]:
    """文字 + 图片可同条；图片过多再拆。"""
    if not non_video:
        return []
    image_count = sum(1 for seg in non_video if seg.type == "image")
    if image_count <= MAX_MEDIA_PER_MESSAGE:
        return [non_video]

    images = Message([seg for seg in non_video if seg.type == "image"])
    caption = Message([seg for seg in non_video if seg.type != "image"])
    chunks = _chunk_media(images)
    if not caption:
        return chunks
    first_image = next(
        (i for i, seg in enumerate(non_video) if seg.type == "image"), None
    )
    first_caption = next(
        (i for i, seg in enumerate(non_video) if seg.type != "image"), None
    )
    if (
        first_caption is not None
        and first_image is not None
        and first_caption < first_image
    ):
        return [caption, *chunks]
    return [*chunks, caption]


def reply_batches(message: Message) -> list[Message]:
    """每个 video 单独一条；文字与图片可同条。

    单次扫描保序：遇到视频先冲刷已有文字/图，再发该视频批，避免
    ``video, image, video`` 被重排成 ``video, video, image``。
    """
    if not message:
        return []

    batches: list[Message] = []
    pending = Message()

    def flush_pending() -> None:
        nonlocal pending
        if pending:
            batches.extend(_text_image_batches(pending))
            pending = Message()

    for seg in message:
        if seg.type == "video":
            flush_pending()
            batches.append(Message([seg]))
            continue
        if seg.type == "text" and not str(seg.data.get("text", "")).strip():
            continue
        pending.append(seg)
    flush_pending()
    return batches
