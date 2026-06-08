"""
直播通知消息发送模块
负责构建和发送直播开播/关播通知消息
参考 stream_notify 的推送方式实现
"""

from datetime import datetime
from typing import Iterable, List, Optional, Union

from nonebot import get_driver
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from utils.bilibili_api import RoomInfo, UserInfo
from shared.config.message_templates import LiveMessageTemplates
from shared.notify.at_all import LIVE_AT_ALL_FALLBACK, bot_can_at_all
from shared.notify.message_template import build_message_from_template

SegmentPart = Union[MessageSegment, str]


class LiveNotificationSender:
    """直播通知发送器"""

    def __init__(
        self,
        include_room_info: bool = True,
        templates: Optional[LiveMessageTemplates] = None,
    ):
        self.include_room_info = include_room_info
        self.templates = templates or LiveMessageTemplates()

    def build_start_message(
        self,
        streamer_name: str,
        room_info: Optional[RoomInfo],
        card_image: Optional[bytes] = None,
        *,
        at_all_enabled: bool = False,
        can_at_all: bool = False,
    ) -> Message:
        """严格按模板顺序构建开播通知消息。"""
        message = Message()

        if at_all_enabled:
            if can_at_all:
                message.append(MessageSegment.at("all"))
            else:
                message.append(LIVE_AT_ALL_FALLBACK)
            message.append(" ")

        text_variables = self._start_text_variables(streamer_name, room_info)

        def card_parts() -> Iterable[SegmentPart]:
            if not card_image:
                return []
            try:
                return [MessageSegment.image(card_image)]
            except Exception as exc:
                logger.warning(f"添加卡片图片到消息失败: {exc}")
                return []

        def cover_parts() -> Iterable[SegmentPart]:
            if card_image or not room_info or not room_info.cover:
                return []
            try:
                return [MessageSegment.image(room_info.cover)]
            except Exception as exc:
                logger.warning(f"添加直播封面失败: {exc}")
                return []

        body = build_message_from_template(
            self.templates.start,
            text_variables,
            {"card": card_parts, "cover": cover_parts},
        )
        return message + body

    def build_end_message(
        self,
        streamer_name: str,
        card_image: Optional[bytes] = None,
        duration_seconds: int = 0,
    ) -> Message:
        """严格按模板顺序构建下播通知消息。"""
        duration_str = self._format_duration(duration_seconds) if duration_seconds > 0 else ""
        text_variables = {
            "streamer_name": streamer_name,
            "duration": duration_str,
        }

        def card_parts() -> Iterable[SegmentPart]:
            if not card_image:
                return []
            try:
                return [MessageSegment.image(card_image)]
            except Exception as exc:
                logger.warning(f"添加下播卡片图片到消息失败: {exc}")
                return []

        return build_message_from_template(
            self.templates.end,
            text_variables,
            {"card": card_parts},
        )

    def _start_text_variables(
        self,
        streamer_name: str,
        room_info: Optional[RoomInfo],
    ) -> dict[str, str]:
        variables = {"streamer_name": streamer_name, "title": "", "time": "", "url": ""}
        if not self.include_room_info or not room_info:
            return variables

        variables["title"] = room_info.title
        variables["url"] = room_info.get_live_url()
        if room_info.live_start_time > 0:
            start_time = datetime.fromtimestamp(room_info.live_start_time)
            variables["time"] = start_time.strftime("%Y-%m-%d %H:%M:%S")
        return variables

    def _format_duration(self, seconds: int) -> str:
        if seconds <= 0:
            return ""

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}小时{minutes}分钟{secs}秒"
        if minutes > 0:
            return f"{minutes}分钟{secs}秒"
        return f"{secs}秒"

    async def _try_generate_card(
        self,
        streamer_name: str,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo],
    ) -> Optional[bytes]:
        """尝试生成开播卡片图片，失败返回 None（触发降级）"""
        try:
            from .card_generator import generate_live_start_card
            return await generate_live_start_card(
                streamer_name=streamer_name,
                user_info=user_info,
                room_info=room_info,
            )
        except Exception as e:
            logger.error(f"生成开播卡片失败，将降级为纯文本通知: {e}")
            return None

    async def _try_generate_end_card(
        self,
        streamer_name: str,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo],
        duration_seconds: int = 0,
    ) -> Optional[bytes]:
        """尝试生成下播卡片图片，失败返回 None（触发降级）"""
        try:
            from .card_generator import generate_live_end_card
            return await generate_live_end_card(
                streamer_name=streamer_name,
                user_info=user_info,
                room_info=room_info,
                duration_seconds=duration_seconds,
            )
        except Exception as e:
            logger.error(f"生成下播卡片失败，将降级为纯文本通知: {e}")
            return None

    async def send_notification(
        self,
        status: str,
        streamer_name: str,
        room_info: Optional[RoomInfo],
        target_groups: List[str],
        user_info: Optional[UserInfo] = None,
        duration_seconds: int = 0,
        at_all_enabled: bool = False,
    ):
        """发送直播通知到指定群组"""
        if not target_groups:
            logger.warning("没有配置目标群组，跳过发送通知")
            return

        logger.info(f"开始发送直播{status}通知 - 主播: {streamer_name}, 目标群组: {target_groups}")

        bots = get_driver().bots

        if not bots:
            logger.warning("没有可用的机器人实例")
            return

        if status == "start":
            card_image = await self._try_generate_card(streamer_name, user_info, room_info)
        else:
            card_image = await self._try_generate_end_card(
                streamer_name, user_info, room_info, duration_seconds
            )

        for bot_id, bot in bots.items():
            if not isinstance(bot, Bot):
                continue

            logger.debug(f"使用机器人 {bot_id} 发送通知")

            for group_id in target_groups:
                try:
                    can_at_all = False
                    if status == "start" and at_all_enabled:
                        can_at_all = await bot_can_at_all(bot, group_id)

                    if status == "start":
                        message = self.build_start_message(
                            streamer_name=streamer_name,
                            room_info=room_info,
                            card_image=card_image,
                            at_all_enabled=at_all_enabled,
                            can_at_all=can_at_all,
                        )
                    else:
                        message = self.build_end_message(
                            streamer_name=streamer_name,
                            card_image=card_image,
                            duration_seconds=duration_seconds,
                        )

                    await bot.send_group_msg(
                        group_id=int(group_id),
                        message=message,
                    )
                    logger.success(f"直播{status}通知已发送到群组 {group_id}")

                except Exception as e:
                    logger.error(f"发送通知到群组 {group_id} 失败: {e}")
                    import traceback
                    logger.debug(f"错误详情: {traceback.format_exc()}")


notification_sender: Optional[LiveNotificationSender] = None


def get_sender(
    include_room_info: bool = True,
    templates: Optional[LiveMessageTemplates] = None,
) -> LiveNotificationSender:
    """获取或创建发送器实例"""
    global notification_sender
    if notification_sender is None:
        notification_sender = LiveNotificationSender(
            include_room_info=include_room_info,
            templates=templates,
        )
    return notification_sender
