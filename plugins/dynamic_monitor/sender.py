"""
动态消息发送模块
负责构建和发送动态通知消息
"""

from typing import List
from nonebot.log import logger

from .models import DynamicItem


class DynamicSender:
    """动态消息发送器"""

    def __init__(self, include_details: bool = True):
        self.include_details = include_details

    def build_dynamic_message(self, dynamic: DynamicItem) -> str:
        """构建动态推送消息"""
        message_parts = []

        # UP主名称和动态类型
        message_parts.append(f"{dynamic.name} {dynamic.get_type_description()}")

        # 动态链接
        message_parts.append(dynamic.url)

        # 如果包含详情且有内容
        if self.include_details:
            if dynamic.content:
                # 限制内容长度
                content = dynamic.content[:200] + "..." if len(dynamic.content) > 200 else dynamic.content
                message_parts.append(f"内容: {content}")

            if dynamic.images:
                message_parts.append(f"包含 {len(dynamic.images)} 张图片")

        return "\n".join(message_parts)

    async def send_to_groups(self, message: str, group_ids: List[str]):
        """发送消息到多个群组"""
        for group_id in group_ids:
            try:
                await self._send_to_group(group_id, message)
                logger.debug(f"成功发送动态到群组 {group_id}")
            except Exception as e:
                logger.error(f"发送消息到群组 {group_id} 失败: {e}")

    async def _send_to_group(self, group_id: str, message: str):
        """发送消息到指定群组"""
        try:
            from nonebot import get_bot
            bot = get_bot()

            # 发送群消息
            await bot.send_group_msg(
                group_id=int(group_id),
                message=message
            )
        except Exception as e:
            logger.error(f"发送消息到群组 {group_id} 失败: {e}")
            raise