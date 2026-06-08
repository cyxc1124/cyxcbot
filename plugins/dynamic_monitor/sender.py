"""
动态消息发送模块
负责构建和发送动态通知消息
"""

from typing import Iterable, List, Optional, Union

from nonebot.log import logger
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from utils.bilibili_api import DynamicItem
from shared.config.message_templates import DynamicMessageTemplates
from shared.notify.at_all import DYNAMIC_AT_ALL_FALLBACK, resolve_at_all_prefix
from shared.notify.message_template import build_message_from_template

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
                    except Exception as exc:
                        logger.warning(f"添加动态图片失败: {image_url}, {exc}")
                return parts

            if screenshot_image:
                try:
                    return [MessageSegment.image(screenshot_image)]
                except Exception as exc:
                    logger.warning(f"添加动态截图失败: {exc}")
            return []

        return build_message_from_template(
            template,
            text_variables,
            {"media": media_parts},
        )

    def _resolve_template(self, is_pinned: bool, is_query: bool, query_type: str) -> str:
        if is_query:
            if query_type == "latest":
                return self.templates.query_latest
            if query_type == "pinned":
                return self.templates.query_pinned
            return self.templates.push
        if is_pinned:
            return self.templates.pinned
        return self.templates.push

    async def send_to_groups(
        self,
        message: Message,
        group_ids: List[str],
        *,
        at_all_enabled: bool = False,
    ):
        """发送消息到多个群组"""
        for group_id in group_ids:
            try:
                await self._send_to_group(group_id, message, at_all_enabled=at_all_enabled)
                logger.debug(f"成功发送动态到群组 {group_id}")
            except Exception as e:
                logger.error(f"发送消息到群组 {group_id} 失败: {e}")

    async def _send_to_group(self, group_id: str, message: Message, *, at_all_enabled: bool = False):
        """发送消息到指定群组"""
        try:
            from nonebot import get_bot
            bot = get_bot()

            if not bot:
                logger.warning(f"机器人未连接，跳过发送到群组 {group_id}")
                return

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

            await bot.send_group_msg(
                group_id=int(group_id),
                message=payload
            )
        except Exception as e:
            logger.error(f"发送消息到群组 {group_id} 失败: {e}")
            raise

    async def send_to_users(self, message: Message, user_ids: List[str]):
        """发送消息到多个好友私聊"""
        for user_id in user_ids:
            try:
                await self._send_to_user(user_id, message)
                logger.debug(f"成功发送动态到好友 {user_id}")
            except Exception as e:
                logger.error(f"发送消息到好友 {user_id} 失败: {e}")

    async def _send_to_user(self, user_id: str, message: Message):
        """发送消息到指定好友"""
        try:
            from nonebot import get_bot
            bot = get_bot()

            if not bot:
                logger.warning(f"机器人未连接，跳过发送到好友 {user_id}")
                return

            await bot.send_private_msg(
                user_id=int(user_id),
                message=message,
            )
        except Exception as e:
            logger.error(f"发送消息到好友 {user_id} 失败: {e}")
            raise
