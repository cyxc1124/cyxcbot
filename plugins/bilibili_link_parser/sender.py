"""链接解析结果消息构建。"""

from datetime import datetime

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from utils.bilibili_api import RoomInfo, UserInfo, VideoInfo
from utils.bilibili_api.live_models import LiveStatus


def build_video_link_message(video: VideoInfo) -> Message:
    """构建视频卡片消息：封面、标题、发布时间、UP 主、链接。"""
    message = Message()

    if video.cover:
        try:
            message.append(MessageSegment.image(video.cover))
        except Exception as exc:
            logger.warning(f"添加视频封面失败: {exc}")

    message.append(f"标题：{video.title}\n")
    message.append(f"UP主：{video.author_name or '未知'}\n")
    message.append(f"发布时间：{video.format_pub_date()}\n")
    message.append(f"链接：{video.get_video_url()}")

    return message


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


def build_live_link_message(room: RoomInfo, user_info: UserInfo | None = None) -> Message:
    """构建直播间卡片消息：封面、标题、主播、状态、开播时间、链接。"""
    message = Message()
    streamer_name = user_info.name if user_info and user_info.name else "未知"

    if room.cover:
        try:
            message.append(MessageSegment.image(room.cover))
        except Exception as exc:
            logger.warning(f"添加直播封面失败: {exc}")

    message.append(f"标题：{room.title or '暂无标题'}\n")
    message.append(f"主播：{streamer_name}\n")
    message.append(f"状态：{_format_live_status(room)}\n")
    message.append(f"开播时间：{_format_live_start_time(room)}\n")
    if room.area_name:
        message.append(f"分区：{room.area_name}\n")
    message.append(f"链接：{room.get_live_url()}")

    return message
