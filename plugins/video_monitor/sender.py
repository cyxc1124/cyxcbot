"""
视频消息发送模块
负责构建和发送视频通知消息
"""

from typing import List, Optional

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from utils.bilibili_api import VideoInfo


class VideoSender:
    """视频消息发送器"""

    def __init__(self):
        pass

    def build_video_message(
        self, videos: List[VideoInfo], uploader_name: str = ""
    ) -> Message:
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
            except Exception:
                logger.opt(exception=True).warning("添加视频封面失败")

        # 第三行：视频标题
        message.append(f"{video.title}\n")
        message.append("\n")

        # 第四行：BV链接
        message.append(f"{video.get_video_url()}")

        return message

    async def send_to_group(
        self, group_id: str, message: Message, bot: Optional[Bot] = None
    ):
        """发送消息到指定群组；优先使用事件 Bot，否则遍历已连接 Bot。"""
        bots: List[Bot] = []
        if bot is not None:
            bots = [bot]
        else:
            bots = [
                item
                for item in get_driver().bots.values()
                if isinstance(item, Bot)
            ]

        if not bots:
            logger.warning("机器人未连接，跳过发送到群组 {}", group_id)
            raise RuntimeError(f"机器人未连接，无法发送到群组 {group_id}")

        errors: List[str] = []
        for candidate in bots:
            try:
                await candidate.send_group_msg(
                    group_id=int(group_id), message=message
                )
                logger.info("成功发送视频消息到群组 {}", group_id)
                return
            except Exception as exc:
                logger.opt(exception=True).error(
                    "机器人 {} 发送消息到群组 {} 失败", candidate.self_id, group_id
                )
                errors.append(str(exc))

        raise RuntimeError(errors[0] if errors else f"发送到群组 {group_id} 失败")
