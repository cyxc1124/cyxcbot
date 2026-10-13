"""
视频消息发送模块
负责构建和发送视频通知消息
"""

from typing import List

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.adapter.outbound import (
    OfficialReplyLimitError,
    official_reply_remaining,
    send_event_message,
    truncate_text,
)
from shared.notify.message_template import safe_text
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
            message.append(safe_text("暂无视频"))
            return message

        # 获取UP主名称
        if not uploader_name and videos:
            uploader_name = videos[0].author_name or "UP主"

        # 只取第一个视频（最新的）
        video = videos[0]

        # 第一行：xxx 最新投稿
        message.append(safe_text(f"【{uploader_name} 最新投稿】\n"))

        # 第二行：视频封面
        if video.cover:
            try:
                message.append(MessageSegment.image(video.cover))
            except Exception:
                logger.opt(exception=True).warning("添加视频封面失败")

        # 第三行：视频标题
        message.append(safe_text(f"{video.title}\n"))
        message.append(safe_text("\n"))

        # 第四行：BV链接
        message.append(safe_text(f"{video.get_video_url()}"))

        return message

    async def send_official_reply(self, bot, event, messages: list[Message]) -> None:
        """先发送所有投稿文案，封面只使用剩余的官方回复预算。"""
        remaining = official_reply_remaining(event)
        if not remaining or not messages:
            return
        omitted_hint = (
            "\n\n官方 Bot 回复次数有限，部分 UP 主结果未展示，请减少本群订阅后重试。"
        )
        text_limit = 2000 - len(omitted_hint)
        captions = [""]
        for message in messages:
            text = message.extract_plain_text()
            if len(text) > text_limit:
                heading, _, link = text.rpartition("\n")
                text = f"{truncate_text(heading, text_limit - len(link) - 1)}\n{link}"
            if captions[-1] and len(captions[-1]) + len(text) + 2 > text_limit:
                captions.append(text)
            else:
                captions[-1] += ("\n\n" if captions[-1] else "") + text
        if len(captions) > remaining:
            captions = captions[:remaining]
            captions[-1] += omitted_hint
        for caption in captions:
            await send_event_message(bot, event, Message(safe_text(caption)))
        for message in messages:
            for segment in message:
                if segment.type != "image":
                    continue
                if not official_reply_remaining(event):
                    return
                try:
                    await send_event_message(bot, event, Message(segment))
                except OfficialReplyLimitError:
                    return
                except Exception:
                    logger.opt(exception=True).warning("发送视频封面失败")
