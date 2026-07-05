"""
动态消息发送模块
负责构建和发送动态通知消息
"""

from typing import Iterable, List, Optional, Tuple, Union

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import DynamicMessageTemplates
from shared.notify.at_all import DYNAMIC_AT_ALL_FALLBACK, resolve_at_all_prefix
from shared.notify.delivery import (
    DeliveryResult,
    TargetDelivery,
    empty_delivery_result,
)
from shared.notify.message_template import build_message_from_template
from utils.bilibili_api import DynamicItem

SegmentPart = Union[MessageSegment, str]


class DynamicSender:
    """动态消息发送器"""

    def __init__(self, templates: Optional[DynamicMessageTemplates] = None):
        self.templates = templates or DynamicMessageTemplates()

    def build_dynamic_message(
        self,
        dynamic: DynamicItem,
        screenshot_image: Optional[bytes] = None,
        is_pinned: bool = False,
        is_query: bool = False,
        query_type: str = "",
        include_dynamic_media: bool = False,
    ) -> Message:
        """严格按模板顺序构建动态推送消息。"""
        template = self._resolve_template(is_pinned, is_query, query_type)
        text_variables = {
            "name": dynamic.name,
            "type_desc": dynamic.get_type_description(),
            "time": dynamic.format_beijing_time(),
            "url": dynamic.url,
            "dynamic_id": str(dynamic.id),
            "uid": str(dynamic.uid),
        }

        def media_parts() -> Iterable[SegmentPart]:
            if include_dynamic_media:
                parts: List[SegmentPart] = []
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
            return []

        return build_message_from_template(
            template,
            text_variables,
            {"media": media_parts},
        )

    def _resolve_template(
        self, is_pinned: bool, is_query: bool, query_type: str
    ) -> str:
        if is_query:
            if query_type == "latest":
                return self.templates.query_latest
            if query_type == "pinned":
                return self.templates.query_pinned
            return self.templates.push
        if is_pinned:
            return self.templates.pinned
        return self.templates.push

    def _valid_bots(self) -> List[Tuple[str, Bot]]:
        return [
            (bot_id, bot)
            for bot_id, bot in get_driver().bots.items()
            if isinstance(bot, Bot)
        ]

    async def send_to_groups(
        self,
        message: Message,
        group_ids: List[str],
        *,
        at_all_enabled: bool = False,
    ) -> DeliveryResult:
        """发送消息到多个群组，返回结构化投递结果。"""
        if not group_ids:
            return empty_delivery_result()

        valid_bots = self._valid_bots()
        if not valid_bots:
            return DeliveryResult(
                targets=[
                    TargetDelivery("group", group_id, False, "没有可用的机器人实例")
                    for group_id in group_ids
                ]
            )

        targets: List[TargetDelivery] = []
        for group_id in group_ids:
            delivery = TargetDelivery("group", group_id, False, "没有可用的机器人实例")
            for _, bot in valid_bots:
                delivery = await self._send_group_via_bot(
                    bot, group_id, message, at_all_enabled=at_all_enabled
                )
                if delivery.success:
                    break
            targets.append(delivery)
        return DeliveryResult(targets=targets)

    async def _send_group_via_bot(
        self,
        bot: Bot,
        group_id: str,
        message: Message,
        *,
        at_all_enabled: bool = False,
    ) -> TargetDelivery:
        try:
            if at_all_enabled:
                prefix = await resolve_at_all_prefix(
                    bot,
                    group_id,
                    enabled=True,
                    fallback=DYNAMIC_AT_ALL_FALLBACK,
                )
                payload = prefix + message
            else:
                payload = message

            await bot.send_group_msg(group_id=int(group_id), message=payload)
            logger.info("动态消息已发送到群组 {}", group_id)
            return TargetDelivery("group", group_id, True)
        except Exception as exc:
            logger.opt(exception=True).error("发送消息到群组 {} 失败", group_id)
            return TargetDelivery("group", group_id, False, str(exc))

    async def send_to_users(
        self, message: Message, user_ids: List[str]
    ) -> DeliveryResult:
        """发送消息到多个好友，返回结构化投递结果。"""
        if not user_ids:
            return empty_delivery_result()

        valid_bots = self._valid_bots()
        if not valid_bots:
            return DeliveryResult(
                targets=[
                    TargetDelivery("user", user_id, False, "没有可用的机器人实例")
                    for user_id in user_ids
                ]
            )

        targets: List[TargetDelivery] = []
        for user_id in user_ids:
            delivery = TargetDelivery("user", user_id, False, "没有可用的机器人实例")
            for _, bot in valid_bots:
                delivery = await self._send_user_via_bot(bot, user_id, message)
                if delivery.success:
                    break
            targets.append(delivery)
        return DeliveryResult(targets=targets)

    async def _send_user_via_bot(
        self, bot: Bot, user_id: str, message: Message
    ) -> TargetDelivery:
        try:
            await bot.send_private_msg(user_id=int(user_id), message=message)
            logger.info("动态消息已发送到好友 {}", user_id)
            return TargetDelivery("user", user_id, True)
        except Exception as exc:
            logger.opt(exception=True).error("发送消息到好友 {} 失败", user_id)
            return TargetDelivery("user", user_id, False, str(exc))

    async def send_message(
        self,
        message: Message,
        group_ids: List[str],
        user_ids: List[str],
        *,
        at_all_enabled: bool = False,
    ) -> DeliveryResult:
        """向群组与好友发送同一条消息，并合并投递结果。"""
        group_result = await self.send_to_groups(
            message, group_ids, at_all_enabled=at_all_enabled
        )
        user_result = await self.send_to_users(message, user_ids)
        return group_result.merge(user_result)
