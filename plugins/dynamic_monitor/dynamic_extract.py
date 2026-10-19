"""Extract dynamic images by ID or by quoting a bot message with a dynamic URL."""

from __future__ import annotations

from typing import Literal

import aiohttp
from nonebot import on_message
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.log import logger

from shared.adapter.inbound import (
    group_id_of,
    is_group_event,
    is_private_event,
    user_id_of,
)
from shared.adapter.outbound import send_event_message
from shared.config.command_aliases import (
    command_aliases_for_event,
    parse_extract_dynamic_id,
)
from shared.config.message_templates import DynamicMessageTemplates
from shared.config.service import get_config_service
from shared.dynamic_subscription import (
    is_group_dynamic_subscribed,
    is_user_dynamic_subscribed,
)
from shared.notify.message_template import (
    build_message_from_template,
    render_message_template,
)
from utils.bilibili_api import DynamicFetcher
from utils.bilibili_api.link_parser import DYNAMIC_URL_PATTERN

from .config import Config

group_dynamic_extract = on_message(priority=4, block=False)
private_dynamic_extract = on_message(priority=4, block=False)


def _register_extract_startup() -> None:
    try:
        from nonebot import get_driver

        driver = get_driver()

        @driver.on_startup
        async def _dynamic_extract_startup() -> None:
            logger.info(
                "动态图片提取 (提取/获取，触发词与前缀可在 Web Admin 自定义) 已就绪，需存在订阅映射"
            )
    except Exception as exc:
        logger.warning(f"动态图片提取: 启动日志注册失败: {exc}")


_register_extract_startup()


def build_extract_reply_message(
    templates: DynamicMessageTemplates,
    dynamic_id: str,
    images: list[str],
    *,
    kind: Literal["success", "empty", "failed"],
) -> Message:
    """Build extract reply from configured templates."""
    url = f"https://t.bilibili.com/{dynamic_id}"
    text_variables = {"dynamic_id": dynamic_id, "url": url}

    if kind == "success":
        template = templates.extract
    elif kind == "empty":
        template = templates.extract_empty
    else:
        template = templates.extract_failed

    segment_handlers = {}
    if kind == "success" and images:
        label_template = templates.extract_image_label

        def images_handler():
            parts: list[MessageSegment | str] = []
            for index, image_url in enumerate(images, start=1):
                label = render_message_template(
                    label_template,
                    {"index": str(index), "dynamic_id": dynamic_id},
                )
                parts.append(f"{label}\n")
                parts.append(MessageSegment.image(image_url))
            return parts

        segment_handlers["images"] = images_handler

    return build_message_from_template(template, text_variables, segment_handlers)


async def _fetch_dynamic_images(dynamic_id: str, cookie: str | None) -> list[str]:
    async with aiohttp.ClientSession() as session:
        fetcher = DynamicFetcher(session, cookie)
        dynamic = await fetcher.fetch_dynamic_detail(dynamic_id, cookie=cookie)
        if not dynamic:
            return []
        return dynamic.images


async def _send_reply(bot: Bot, event: Event, message: Message | str) -> None:
    payload = message if isinstance(message, Message) else Message(str(message))
    await send_event_message(bot, event, payload)


def _quoted_dynamic_id(bot: Bot, event: Event) -> str | None:
    if not isinstance(event, MessageEvent):
        return None
    reply = event.reply
    if reply is None or str(reply.sender.user_id) != str(bot.self_id):
        return None
    dynamic_ids = {
        next(group for group in match.groups() if group)
        for match in DYNAMIC_URL_PATTERN.finditer(reply.message.extract_plain_text())
    }
    return dynamic_ids.pop() if len(dynamic_ids) == 1 else None


def _subscription_allowed(event: Event) -> bool:
    snap = get_config_service().get_snapshot()
    if is_group_event(event):
        group_id = group_id_of(event)
        return bool(group_id) and is_group_dynamic_subscribed(group_id, snap)
    return is_user_dynamic_subscribed(user_id_of(event), snap)


async def _handle_extract(bot: Bot, event: Event) -> None:
    user_id = user_id_of(event)
    if is_group_event(event) and user_id == str(getattr(bot, "self_id", "")):
        return

    message_text = event.get_plaintext().strip()
    snap = get_config_service().get_snapshot()
    dynamic_id = parse_extract_dynamic_id(
        message_text, await command_aliases_for_event(snap, bot, event)
    )
    if dynamic_id is None:
        return

    if not _subscription_allowed(event):
        scope = "群" if is_group_event(event) else "好友"
        target = (
            f"group={group_id_of(event)}"
            if is_group_event(event)
            else f"user={user_id}"
        )
        logger.warning(
            f"拒绝提取动态图片: id={dynamic_id} user={user_id} {target} "
            f"scope={scope} reason=no_subscription"
        )
        return

    if not dynamic_id:
        dynamic_id = _quoted_dynamic_id(bot, event)
        if not dynamic_id:
            await _send_reply(
                bot,
                event,
                "无法确定要提取的动态，请引用机器人发送且包含动态链接的消息，"
                "或在提取命令后填写动态ID。",
            )
            return

    config = Config.from_service()
    templates = config.message_templates
    cookie = config.bilibili_cookie or None
    if not cookie:
        logger.warning("提取动态图片：未配置 Cookie，部分动态可能无法访问")

    logger.info(f"提取动态图片: id={dynamic_id} user={user_id}")

    try:
        images = await _fetch_dynamic_images(dynamic_id, cookie)
    except Exception as exc:
        logger.error(f"提取动态 {dynamic_id} 图片失败: {exc}")
        reply = build_extract_reply_message(templates, dynamic_id, [], kind="failed")
        await _send_reply(bot, event, reply)
        return

    if not images:
        reply = build_extract_reply_message(templates, dynamic_id, [], kind="empty")
    else:
        reply = build_extract_reply_message(
            templates, dynamic_id, images, kind="success"
        )

    await _send_reply(bot, event, reply)
    logger.info(f"已回复动态 {dynamic_id} 图片提取: count={len(images)}")


@group_dynamic_extract.handle()
async def handle_group_dynamic_extract(bot: Bot, event: Event):
    if not is_group_event(event):
        return
    await _handle_extract(bot, event)


@private_dynamic_extract.handle()
async def handle_private_dynamic_extract(bot: Bot, event: Event):
    if not is_private_event(event):
        return
    await _handle_extract(bot, event)
