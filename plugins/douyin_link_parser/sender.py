"""抖音链接解析结果消息构建。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import DouyinLinkMessageTemplates
from shared.notify.message_template import build_message_from_template
from utils.douyin_api import DouyinMediaItem, DouyinVideoResult

SegmentPart = Union[MessageSegment, str]

# QQ / NapCat：同条消息里 video 段常吞掉后续文字；图集（纯 image）可混排。
_MEDIA_SEG_TYPES = frozenset({"video", "image"})
# QQ NT sendMsg 同条图片过多会 result=34（实测 26 张失败）；按批拆分。
MAX_MEDIA_PER_MESSAGE = 10


def _video_parts(file_path: Path) -> Iterable[SegmentPart]:
    if not file_path.exists():
        return []
    try:
        if file_path.stat().st_size <= 0:
            logger.warning("抖音视频文件为空: {}", file_path)
            return []
        # 传 Path → file://；协议端须与 bot 同路径可见（共享媒体目录）。
        return [MessageSegment.video(file_path.resolve())]
    except Exception:
        logger.opt(exception=True).warning("添加抖音视频段失败: {}", file_path)
        return []


def _image_parts(file_path: Path) -> Iterable[SegmentPart]:
    if not file_path.exists():
        return []
    try:
        if file_path.stat().st_size <= 0:
            logger.warning("抖音图片文件为空: {}", file_path)
            return []
        return [MessageSegment.image(file_path.resolve())]
    except Exception:
        logger.opt(exception=True).warning("添加抖音图片段失败: {}", file_path)
        return []


def _media_parts(result: DouyinVideoResult) -> Iterable[SegmentPart]:
    """Expand ``{video}`` to all media: static images + Live/video segments."""
    items = list(result.items) if result.items else []
    if not items and result.file_path:
        items = [DouyinMediaItem(kind="video", file_path=result.file_path)]

    parts: list[SegmentPart] = []
    for item in items:
        if item.kind == "image":
            parts.extend(_image_parts(item.file_path))
        else:
            parts.extend(_video_parts(item.file_path))
    return parts


def build_douyin_link_message(
    result: DouyinVideoResult,
    templates: Optional[DouyinLinkMessageTemplates] = None,
) -> Message:
    tpl = templates or DouyinLinkMessageTemplates()
    text_variables = {
        "title": result.title or "暂无标题",
        "author": result.author or "未知",
        "url": result.share_url or "",
        "aweme_id": result.aweme_id or "",
    }
    return build_message_from_template(
        tpl.video,
        text_variables,
        {"video": lambda: _media_parts(result)},
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
    """Split for QQ limits: video↔text 不可混；同条图片过多会 sendMsg result=34。"""
    if not message:
        return []
    media, caption = split_media_and_caption(message)
    if not media:
        return [caption] if caption else []

    has_video = any(seg.type == "video" for seg in media)
    media_chunks = _chunk_media(media)

    # 少量纯图 + 文案可同条（图集小合集）
    if (
        not has_video
        and len(media_chunks) == 1
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
