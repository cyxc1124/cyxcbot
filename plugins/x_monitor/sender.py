"""X 推文消息发送模块。"""

from typing import Iterable, List, Optional, Tuple, Union

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import XMessageTemplates
from shared.notify.at_all import X_AT_ALL_FALLBACK, resolve_at_all_prefix
from shared.notify.delivery import (
    DeliveryResult,
    TargetDelivery,
    empty_delivery_result,
)
from shared.notify.message_template import build_message_from_template
from utils.x_api import TweetItem

SegmentPart = Union[MessageSegment, str]


class XSender:
    """X 推文消息发送器。"""

    def __init__(self, templates: Optional[XMessageTemplates] = None):
        self.templates = templates or XMessageTemplates()

    def build_tweet_message(self, tweet: TweetItem) -> Message:
        """严格按模板顺序构建推文推送消息。"""
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
                    logger.opt(exception=True).warning(
                        "添加推文图片失败: {}", image_url
                    )
            return parts

        return build_message_from_template(
            self.templates.push,
            text_variables,
            {"media": media_parts},
        )

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
                    fallback=X_AT_ALL_FALLBACK,
                )
                payload = prefix + message
            else:
                payload = message

            await bot.send_group_msg(group_id=int(group_id), message=payload)
            logger.info("X 推文消息已发送到群组 {}", group_id)
            return TargetDelivery("group", group_id, True)
        except Exception as exc:
            logger.opt(exception=True).error("发送消息到群组 {} 失败", group_id)
            return TargetDelivery("group", group_id, False, str(exc))

    async def send_to_users(
        self, message: Message, user_ids: List[str]
    ) -> DeliveryResult:
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
            logger.info("X 推文消息已发送到好友 {}", user_id)
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
        group_result = await self.send_to_groups(
            message, group_ids, at_all_enabled=at_all_enabled
        )
        user_result = await self.send_to_users(message, user_ids)
        return group_result.merge(user_result)
