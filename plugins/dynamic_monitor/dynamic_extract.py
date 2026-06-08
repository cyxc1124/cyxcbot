"""Extract all images from a Bilibili dynamic via #提取/#获取{dynamic_id}."""

from __future__ import annotations

import re

import aiohttp
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment, PrivateMessageEvent
from nonebot.log import logger

from shared.config.service import get_config_service
from shared.dynamic_subscription import is_group_dynamic_subscribed, is_user_dynamic_subscribed
from utils.bilibili_api import DynamicFetcher

from .config import Config

EXTRACT_PATTERN = re.compile(
    r"^#(?:提取|获取)(?:"
    r"https?://(?:www\.)?bilibili\.com/opus/(\d+)|"
    r"https?://t\.bilibili\.com/(\d+)|"
    r"(\d{10,})"
    r")\s*$",
    re.IGNORECASE,
)

group_dynamic_extract = on_message(priority=4, block=False)
private_dynamic_extract = on_message(priority=4, block=False)


def parse_extract_dynamic_id(message_text: str) -> str | None:
    """Return dynamic ID from '#提取/#获取{id|url}' message, or None."""
    match = EXTRACT_PATTERN.match(message_text.strip())
    if not match:
        return None
    return next((group for group in match.groups() if group), None)


def build_extract_images_message(dynamic_id: str, images: list[str]) -> Message:
    """Build reply: header, labeled images, dynamic URL."""
    message = Message()
    message.append(f"动态{dynamic_id}的图片\n")
    for index, image_url in enumerate(images, start=1):
        message.append(f"图片{index}\n")
        message.append(MessageSegment.image(image_url))
    message.append(f"\nhttps://t.bilibili.com/{dynamic_id}")
    return message


async def _fetch_dynamic_images(dynamic_id: str, cookie: str | None) -> list[str]:
    async with aiohttp.ClientSession() as session:
        fetcher = DynamicFetcher(session, cookie)
        dynamic = await fetcher.fetch_dynamic_detail(dynamic_id, cookie=cookie)
        if not dynamic:
            return []
        return dynamic.images


async def _send_reply(
    bot: Bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    message: Message | str,
) -> None:
    if isinstance(event, GroupMessageEvent):
        await bot.send_group_msg(group_id=event.group_id, message=message)
    else:
        await bot.send_private_msg(user_id=event.user_id, message=message)


def _subscription_allowed(event: GroupMessageEvent | PrivateMessageEvent) -> bool:
    snap = get_config_service().get_snapshot()
    if isinstance(event, GroupMessageEvent):
        return is_group_dynamic_subscribed(str(event.group_id), snap)
    return is_user_dynamic_subscribed(str(event.user_id), snap)


async def _handle_extract(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent) -> None:
    if isinstance(event, GroupMessageEvent) and str(event.user_id) == str(event.self_id):
        return

    message_text = event.get_plaintext().strip()
    dynamic_id = parse_extract_dynamic_id(message_text)
    if not dynamic_id:
        return

    if not _subscription_allowed(event):
        scope = "群" if isinstance(event, GroupMessageEvent) else "好友"
        await _send_reply(
            bot,
            event,
            Message(
                f"动态{dynamic_id}的图片\n"
                f"该{scope}未配置任何 UP 主动态订阅映射，无法提取图片。\n"
                "请在「动态订阅」中添加 UP 主与推送目标的映射（无需开启推送）。"
            ),
        )
        logger.info(
            f"拒绝提取动态图片: id={dynamic_id} user={event.user_id} reason=no_subscription"
        )
        return

    config = Config.from_service()
    cookie = config.bilibili_cookie or None
    if not cookie:
        logger.warning("提取动态图片：未配置 Cookie，部分动态可能无法访问")

    logger.info(f"提取动态图片: id={dynamic_id} user={event.user_id}")

    try:
        images = await _fetch_dynamic_images(dynamic_id, cookie)
    except Exception as exc:
        logger.error(f"提取动态 {dynamic_id} 图片失败: {exc}")
        await _send_reply(
            bot,
            event,
            Message(f"动态{dynamic_id}的图片\n提取失败，请稍后重试\n\nhttps://t.bilibili.com/{dynamic_id}"),
        )
        return

    if not images:
        reply = Message(
            f"动态{dynamic_id}的图片\n该动态未找到可提取的图片\n\nhttps://t.bilibili.com/{dynamic_id}"
        )
    else:
        reply = build_extract_images_message(dynamic_id, images)

    await _send_reply(bot, event, reply)
    logger.info(f"已回复动态 {dynamic_id} 图片提取: count={len(images)}")


@group_dynamic_extract.handle()
async def handle_group_dynamic_extract(bot: Bot, event: GroupMessageEvent):
    await _handle_extract(bot, event)


@private_dynamic_extract.handle()
async def handle_private_dynamic_extract(bot: Bot, event: PrivateMessageEvent):
    await _handle_extract(bot, event)
