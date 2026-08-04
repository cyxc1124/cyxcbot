"""抖音链接解析结果消息构建。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import DouyinLinkMessageTemplates
from shared.notify.message_template import build_message_from_template
from utils.douyin_api import DouyinVideoResult

SegmentPart = Union[MessageSegment, str]


def _video_parts(file_path: Path) -> Iterable[SegmentPart]:
    if not file_path.exists():
        return []
    try:
        # OneBot: local file path; file:// helps some protocol implementations
        return [MessageSegment.video(f"file://{file_path.resolve()}")]
    except Exception:
        logger.opt(exception=True).warning("添加抖音视频段失败: {}", file_path)
        return []


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
        {"video": lambda: _video_parts(result.file_path)},
    )
