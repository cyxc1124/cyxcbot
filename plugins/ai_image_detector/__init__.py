"""Reply to a quoted image with ai吗？ to inspect its provenance."""

import asyncio

import aiohttp
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

from shared.adapter.outbound import send_event_message
from shared.config.service import get_config_service

from .c2pa_check import inspect_c2pa
from .image import ImageDetectionError, download_image, image_media_type
from .openai_check import check_openai
from .report import build_report

__plugin_meta__ = PluginMetadata(
    name="AI 图片检测",
    description="引用图片检查 C2PA 凭证和 OpenAI SynthID 水印",
    usage="引用一张图片回复 ai吗？（不需要命令前缀）",
    type="application",
    supported_adapters={"~onebot.v11"},
)

_detection_lock = asyncio.Lock()


def is_ai_image_command(event: MessageEvent) -> bool:
    return event.get_plaintext().strip().casefold() in {"ai吗", "ai吗?", "ai吗？"}


ai_image_command = on_message(rule=Rule(is_ai_image_command), priority=5, block=True)


async def detect_quoted_image(bot: Bot, event: MessageEvent) -> str:
    images = event.reply.message["image"] if event.reply else []
    if len(images) != 1:
        return "请引用一条只包含一张图片的消息，回复「ai吗？」。"
    segment = images[0]
    url = segment.data.get("url")
    if not url:
        file = segment.data.get("file")
        if not file:
            return "引用的图片没有可下载地址，请重新发送原图。"
        if isinstance(file, str) and file.startswith(("http://", "https://")):
            url = file
        else:
            info = await bot.get_image(file=file)
            url = info.get("url")
    if not isinstance(url, str):
        return "引用的图片没有可下载地址，请重新发送原图。"
    data = await download_image(url)
    media_type = await asyncio.to_thread(image_media_type, data)
    local = await asyncio.to_thread(inspect_c2pa, data)
    key = get_config_service().get_snapshot().ai_image_openai_api_key
    remote = None
    remote_error = ""
    if key:
        try:
            remote = await check_openai(data, media_type, key)
        except ImageDetectionError as exc:
            remote_error = str(exc)
    return build_report(local, remote, remote_error)


@ai_image_command.handle()
async def handle_ai_image(bot: Bot, event: MessageEvent) -> None:
    if not is_ai_image_command(event):
        return
    if _detection_lock.locked():
        await send_event_message(
            bot, event, Message(MessageSegment.text("图片检测正在进行，请稍后再试。"))
        )
        return
    async with _detection_lock:
        try:
            text = await detect_quoted_image(bot, event)
        except ImageDetectionError as exc:
            text = str(exc)
        except aiohttp.ClientError, TimeoutError:
            text = "图片下载失败或超时，请重新发送原图后再试。"
        except Exception as exc:
            # 原始异常可能含图片签名 URL，日志仅保留异常类型。
            logger.opt(exception=RuntimeError(type(exc).__name__)).error(
                "AI 图片检测失败"
            )
            text = "图片检测失败，本次无法判断，请稍后重试。"
        await send_event_message(bot, event, Message(MessageSegment.text(text)))
