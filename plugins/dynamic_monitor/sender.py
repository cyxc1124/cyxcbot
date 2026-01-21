"""
动态消息发送模块
负责构建和发送动态通知消息
"""

from typing import List, Optional
from nonebot.log import logger
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from utils.bilibili_api import DynamicItem


class DynamicSender:
    """动态消息发送器"""

    def __init__(self, enable_screenshot: bool = True):
        self.enable_screenshot = enable_screenshot

    def build_dynamic_message(self, dynamic: DynamicItem, screenshot_image: Optional[bytes] = None, is_pinned: bool = False, is_query: bool = False, query_type: str = "") -> Message:
        """构建动态推送消息

        Args:
            dynamic: 动态对象
            screenshot_image: 截图数据
            is_pinned: 是否为置顶动态变更通知
            is_query: 是否为主动查询
            query_type: 查询类型 ("latest" 或 "pinned")
        """
        message = Message()

        # 第一行：根据消息类型构建不同的标题
        if is_query:
            if query_type == "latest":
                message.append(f"【{dynamic.name} 的最新动态】\n")
            elif query_type == "pinned":
                message.append(f"【{dynamic.name} 的置顶动态】\n")
        elif is_pinned:
            # 置顶动态变更通知
            message.append(f"{dynamic.name} 置顶了动态\n")
        else:
            # 普通动态推送
            message.append(f"{dynamic.name} {dynamic.get_type_description()}\n")

        # 对于非查询消息，添加时间和截图
        if not is_query:
            message.append(f"{dynamic.format_beijing_time()}\n")

        # 如果启用了截图且有截图数据，添加图片
        if self.enable_screenshot and screenshot_image:
            try:
                message.append(MessageSegment.image(screenshot_image))
                message.append("")  # 添加空行
            except Exception as e:
                logger.warning(f"添加动态截图失败: {e}")

        # 动态链接
        message.append(f"{dynamic.url}")

        return message

    async def send_to_groups(self, message: Message, group_ids: List[str]):
        """发送消息到多个群组"""
        for group_id in group_ids:
            try:
                await self._send_to_group(group_id, message)
                logger.debug(f"成功发送动态到群组 {group_id}")
            except Exception as e:
                logger.error(f"发送消息到群组 {group_id} 失败: {e}")

    async def _send_to_group(self, group_id: str, message: Message):
        """发送消息到指定群组"""
        try:
            from nonebot import get_bot
            bot = get_bot()

            if not bot:
                logger.warning(f"机器人未连接，跳过发送到群组 {group_id}")
                return

            # 发送群消息
            await bot.send_group_msg(
                group_id=int(group_id),
                message=message
            )
        except Exception as e:
            logger.error(f"发送消息到群组 {group_id} 失败: {e}")
            raise