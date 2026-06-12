"""
直播通知消息发送模块
负责构建和发送直播开播/关播通知消息
参考 stream_notify 的推送方式实现
"""

import asyncio
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple, Union

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import LiveMessageTemplates
from shared.notify.at_all import LIVE_AT_ALL_FALLBACK, bot_can_at_all
from shared.notify.message_template import build_message_from_template
from utils.bilibili_api import RoomInfo, UserInfo

from .card_generator import PrefetchImages

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

    def template_uses_card(self, status: str) -> bool:
        """模板是否包含 {card} 占位符。"""
        template = self.templates.start if status == "start" else self.templates.end
        return "{card}" in template

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
        duration_str = (
            self._format_duration(duration_seconds) if duration_seconds > 0 else ""
        )
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
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> Optional[bytes]:
        """尝试生成开播卡片图片，失败返回 None（触发降级）"""
        try:
            from .card_generator import generate_live_start_card

            return await generate_live_start_card(
                streamer_name=streamer_name,
                user_info=user_info,
                room_info=room_info,
                prefetched_images=prefetched_images,
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
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> Optional[bytes]:
        """尝试生成下播卡片图片，失败返回 None（触发降级）"""
        try:
            from .card_generator import generate_live_end_card

            return await generate_live_end_card(
                streamer_name=streamer_name,
                user_info=user_info,
                room_info=room_info,
                duration_seconds=duration_seconds,
                prefetched_images=prefetched_images,
            )
        except Exception as e:
            logger.error(f"生成下播卡片失败，将降级为纯文本通知: {e}")
            return None

    async def _generate_card_if_needed(
        self,
        status: str,
        streamer_name: str,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo],
        duration_seconds: int,
        prefetched_images: Optional[PrefetchImages],
    ) -> Optional[bytes]:
        if not self.template_uses_card(status):
            return None

        if status == "start":
            return await self._try_generate_card(
                streamer_name, user_info, room_info, prefetched_images
            )
        return await self._try_generate_end_card(
            streamer_name,
            user_info,
            room_info,
            duration_seconds,
            prefetched_images,
        )

    async def _resolve_at_all_map(
        self,
        bot: Bot,
        target_groups: List[str],
        *,
        status: str,
        at_all_enabled: bool,
    ) -> Dict[str, bool]:
        if status != "start" or not at_all_enabled or not target_groups:
            return {group_id: False for group_id in target_groups}

        results = await asyncio.gather(
            *[bot_can_at_all(bot, group_id) for group_id in target_groups],
            return_exceptions=True,
        )
        return {
            group_id: result if isinstance(result, bool) else False
            for group_id, result in zip(target_groups, results)
        }

    async def _send_group_message(
        self,
        bot: Bot,
        group_id: str,
        message: Message,
        status: str,
    ) -> None:
        try:
            await bot.send_group_msg(
                group_id=int(group_id),
                message=message,
            )
            logger.success(f"直播{status}通知已发送到群组 {group_id}")
        except Exception as e:
            logger.error(f"发送通知到群组 {group_id} 失败: {e}")
            import traceback

            logger.debug(f"错误详情: {traceback.format_exc()}")

    async def _send_private_message(
        self,
        bot: Bot,
        user_id: str,
        message: Message,
        status: str,
    ) -> None:
        try:
            await bot.send_private_msg(
                user_id=int(user_id),
                message=message,
            )
            logger.success(f"直播{status}通知已发送到好友 {user_id}")
        except Exception as e:
            logger.error(f"发送通知到好友 {user_id} 失败: {e}")
            import traceback

            logger.debug(f"错误详情: {traceback.format_exc()}")

    async def send_notification(
        self,
        status: str,
        streamer_name: str,
        room_info: Optional[RoomInfo],
        target_groups: List[str],
        user_info: Optional[UserInfo] = None,
        duration_seconds: int = 0,
        at_all_enabled: bool = False,
        target_users: Optional[List[str]] = None,
        prefetched_images: Optional[PrefetchImages] = None,
    ):
        """发送直播通知到指定群组与好友"""
        target_users = target_users or []
        if not target_groups and not target_users:
            logger.warning("没有配置推送目标，跳过发送通知")
            return

        logger.info(
            f"开始发送直播{status}通知 - 主播: {streamer_name}, "
            f"目标群组: {target_groups}, 目标好友: {target_users}"
        )

        bots = get_driver().bots

        if not bots:
            logger.warning("没有可用的机器人实例")
            return

        valid_bots: List[Tuple[str, Bot]] = [
            (bot_id, bot) for bot_id, bot in bots.items() if isinstance(bot, Bot)
        ]
        if not valid_bots:
            logger.warning("没有可用的 OneBot 机器人实例")
            return

        parallel_tasks: List = [
            self._generate_card_if_needed(
                status,
                streamer_name,
                user_info,
                room_info,
                duration_seconds,
                prefetched_images,
            )
        ]
        for _, bot in valid_bots:
            parallel_tasks.append(
                self._resolve_at_all_map(
                    bot,
                    target_groups,
                    status=status,
                    at_all_enabled=at_all_enabled,
                )
            )

        parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)

        card_image: Optional[bytes] = None
        card_result = parallel_results[0]
        if isinstance(card_result, Exception):
            logger.error(f"生成直播{status}卡片失败: {card_result}")
        else:
            card_image = card_result

        at_all_maps: List[Dict[str, bool]] = []
        for result in parallel_results[1:]:
            if isinstance(result, Exception):
                logger.error(f"查询 @全体 权限失败: {result}")
                at_all_maps.append({group_id: False for group_id in target_groups})
            else:
                at_all_maps.append(result)

        send_tasks: List = []
        for index, (bot_id, bot) in enumerate(valid_bots):
            logger.debug(f"使用机器人 {bot_id} 发送通知")
            at_all_map = (
                at_all_maps[index]
                if index < len(at_all_maps)
                else {group_id: False for group_id in target_groups}
            )

            for group_id in target_groups:
                if status == "start":
                    message = self.build_start_message(
                        streamer_name=streamer_name,
                        room_info=room_info,
                        card_image=card_image,
                        at_all_enabled=at_all_enabled,
                        can_at_all=at_all_map.get(group_id, False),
                    )
                else:
                    message = self.build_end_message(
                        streamer_name=streamer_name,
                        card_image=card_image,
                        duration_seconds=duration_seconds,
                    )

                send_tasks.append(
                    self._send_group_message(bot, group_id, message, status)
                )

            for user_id in target_users:
                if status == "start":
                    message = self.build_start_message(
                        streamer_name=streamer_name,
                        room_info=room_info,
                        card_image=card_image,
                        at_all_enabled=False,
                        can_at_all=False,
                    )
                else:
                    message = self.build_end_message(
                        streamer_name=streamer_name,
                        card_image=card_image,
                        duration_seconds=duration_seconds,
                    )

                send_tasks.append(
                    self._send_private_message(bot, user_id, message, status)
                )

        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)


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
