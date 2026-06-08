"""
视频消息发送模块
负责构建和发送视频通知消息
"""

from typing import List, Optional
from nonebot.log import logger
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from utils.bilibili_api import VideoInfo


class VideoSender:
    """视频消息发送器"""

    def __init__(self):
        pass

    def build_video_message(self, videos: List[VideoInfo], uploader_name: str = "") -> Message:
        """构建视频列表消息

        消息格式：
        第一行：xxx 最新投稿
        第二行：视频封面
        第三行：视频标题
        第四行：BV链接

        Args:
            videos: 视频列表
            uploader_name: UP主名称（可选，如果视频列表中有会自动取）
        """
        message = Message()

        if not videos:
            message.append("暂无视频")
            return message

        # 获取UP主名称
        if not uploader_name and videos:
            uploader_name = videos[0].author_name or "UP主"

        # 只取第一个视频（最新的）
        video = videos[0]

        # 第一行：xxx 最新投稿
        message.append(f"【{uploader_name} 最新投稿】\n")

        # 第二行：视频封面
        if video.cover:
            try:
                message.append(MessageSegment.image(video.cover))
            except Exception as e:
                logger.warning(f"添加视频封面失败: {e}")

        # 第三行：视频标题
        message.append(f"{video.title}\n")
        message.append("\n")

        # 第四行：BV链接
        message.append(f"{video.get_video_url()}")

        return message

    async def send_to_group(self, group_id: str, message: Message):
        """发送消息到指定群组"""
        try:
            from nonebot import get_bot
            bot = get_bot()

            if not bot:
                logger.warning(f"机器人未连接，跳过发送到群组 {group_id}")
                return

            await bot.send_group_msg(
                group_id=int(group_id),
                message=message
            )
            logger.info(f"成功发送视频消息到群组 {group_id}")
        except Exception as e:
            logger.error(f"发送消息到群组 {group_id} 失败: {e}")
            raise
