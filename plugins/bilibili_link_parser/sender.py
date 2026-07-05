"""链接解析结果消息构建。"""

from datetime import datetime
from typing import Iterable, Optional, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import LinkMessageTemplates
from shared.notify.message_template import build_message_from_template
from utils.bilibili_api import DynamicItem, RoomInfo, UserInfo, VideoInfo
from utils.bilibili_api.live_models import LiveStatus

SegmentPart = Union[MessageSegment, str]


def _format_live_status(room: RoomInfo) -> str:
    if room.live_status == LiveStatus.LIVE:
        return "直播中"
    if room.live_status == LiveStatus.ROUND:
        return "轮播中"
    return "未开播"


def _format_live_start_time(room: RoomInfo) -> str:
    if room.live_status != LiveStatus.LIVE or room.live_start_time <= 0:
        return "—"
    return datetime.fromtimestamp(room.live_start_time).strftime("%Y-%m-%d %H:%M:%S")


def _cover_parts(cover_url: str | None) -> Iterable[SegmentPart]:
    if not cover_url:
        return []
    try:
        return [MessageSegment.image(cover_url)]
    except Exception as exc:
        logger.warning(f"添加封面失败: {exc}")
        return []


def _dynamic_cover_parts(
    dynamic: DynamicItem,
    *,
    screenshot_image: bytes | None = None,
    include_dynamic_media: bool = False,
) -> Iterable[SegmentPart]:
    """与动态监控一致：优先网页截图，失败或未启用时降级为 API 图片。"""
    if include_dynamic_media:
        parts: list[SegmentPart] = []
        if dynamic.body_text:
            parts.append(f"{dynamic.body_text}\n")
        for image_url in dynamic.images:
            try:
                parts.append(MessageSegment.image(image_url))
            except Exception:
                logger.opt(exception=True).warning(
                    "添加动态图片失败: {}", image_url
                )
        return parts
    if screenshot_image:
        try:
            return [MessageSegment.image(screenshot_image)]
        except Exception:
            logger.opt(exception=True).warning("添加动态截图失败")
    return _cover_parts(dynamic.images[0] if dynamic.images else None)


def build_video_link_message(
    video: VideoInfo,
    templates: Optional[LinkMessageTemplates] = None,
) -> Message:
    """严格按模板顺序构建视频链接解析消息。"""
    tpl = templates or LinkMessageTemplates()
    text_variables = {
        "title": video.title or "暂无标题",
        "author": video.author_name or "未知",
        "pub_date": video.format_pub_date(),
        "url": video.get_video_url(),
        "bvid": video.bvid or "",
        "aid": str(video.aid) if video.aid else "",
    }
    return build_message_from_template(
        tpl.video,
        text_variables,
        {"cover": lambda: _cover_parts(video.cover)},
    )


def build_live_link_message(
    room: RoomInfo,
    user_info: UserInfo | None = None,
    templates: Optional[LinkMessageTemplates] = None,
) -> Message:
    """严格按模板顺序构建直播间链接解析消息。"""
    tpl = templates or LinkMessageTemplates()
    streamer_name = user_info.name if user_info and user_info.name else "未知"
    text_variables = {
        "title": room.title or "暂无标题",
        "streamer_name": streamer_name,
        "status": _format_live_status(room),
        "live_start_time": _format_live_start_time(room),
        "area": room.area_name or "",
        "url": room.get_live_url(),
        "room_id": str(room.room_id),
    }
    return build_message_from_template(
        tpl.live,
        text_variables,
        {"cover": lambda: _cover_parts(room.cover)},
    )


def build_dynamic_link_message(
    dynamic: DynamicItem,
    templates: Optional[LinkMessageTemplates] = None,
    *,
    screenshot_image: bytes | None = None,
    include_dynamic_media: bool = False,
) -> Message:
    """复用视频链接模板构建动态/opus 链接解析消息。"""
    tpl = templates or LinkMessageTemplates()
    title = (dynamic.title or dynamic.body_text or dynamic.get_type_description()).strip()
    if len(title) > 100:
        title = f"{title[:100]}…"
    text_variables = {
        "title": title or "暂无标题",
        "author": dynamic.name or "未知",
        "pub_date": dynamic.format_beijing_time(),
        "url": dynamic.url or f"https://www.bilibili.com/opus/{dynamic.id}",
        "bvid": "",
        "aid": "",
    }
    return build_message_from_template(
        tpl.video,
        text_variables,
        {
            "cover": lambda: _dynamic_cover_parts(
                dynamic,
                screenshot_image=screenshot_image,
                include_dynamic_media=include_dynamic_media,
            )
        },
    )
