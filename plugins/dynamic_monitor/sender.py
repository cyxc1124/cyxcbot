"""
动态消息发送模块
负责构建和发送动态通知消息
"""

from typing import List, Optional
from nonebot.log import logger
from nonebot.adapters.onebot.v11.message import MessageSegment

from .models import DynamicItem


class DynamicSender:
    """动态消息发送器"""

    def __init__(self, include_details: bool = True, enable_screenshot: bool = True):
        self.include_details = include_details
        self.enable_screenshot = enable_screenshot

    def build_dynamic_message(self, dynamic: DynamicItem, screenshot_image: Optional[bytes] = None) -> str:
        """构建动态推送消息"""
        from nonebot.adapters.onebot.v11.message import Message, MessageSegment

        message = Message()

        # UP主名称和动态类型
        message.append(f"{dynamic.name} {dynamic.get_type_description()}")

        # 如果启用了截图且有截图数据，添加图片
        if self.enable_screenshot and screenshot_image:
            try:
                message.append(MessageSegment.image(screenshot_image))
                message.append("")  # 添加空行
            except Exception as e:
                logger.warning(f"添加动态截图失败: {e}")

        # 动态链接
        message.append(dynamic.url)

        # 如果包含详情且有内容
        if self.include_details:
            if dynamic.content:
                # 限制内容长度
                content = dynamic.content[:200] + "..." if len(dynamic.content) > 200 else dynamic.content
                message.append(f"内容: {content}")

            if dynamic.images and not self.enable_screenshot:
                # 如果没有启用截图但有图片信息，才显示图片数量
                message.append(f"包含 {len(dynamic.images)} 张图片")

        return message

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