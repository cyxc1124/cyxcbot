"""
抖音链接自动解析插件

识别群聊/好友中的抖音分享链接，下载视频并以视频消息回传。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.config.douyin_link_parser_policy import resolve_douyin_link_parser_policy
from shared.config.service import get_config_service
from utils.douyin_api import (
    DouyinResolveError,
    extract_douyin_urls,
    resolve_and_download,
)

from .config import Config, get_config, reload_config
from .message_text import collect_message_text
from .sender import build_douyin_link_message

__plugin_meta__ = PluginMetadata(
    name="抖音链接解析",
    description="自动解析群聊/好友中的抖音分享链接并回传视频",
    usage="发送含抖音短链或作品链接即可触发",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

group_douyin_link_parser = on_message(priority=4, block=False)
private_douyin_link_parser = on_message(priority=4, block=False)


async def _handle_douyin_link_message(
    bot: Bot, event: GroupMessageEvent | PrivateMessageEvent
) -> None:
    config = get_config()
    snap = get_config_service().get_snapshot()

    if isinstance(event, PrivateMessageEvent):
        scope = resolve_douyin_link_parser_policy(
            snap,
            user_id=str(event.user_id),
            is_private=True,
        )
    else:
        if str(event.user_id) == str(event.self_id):
            return
        scope = resolve_douyin_link_parser_policy(
            snap,
            group_id=str(event.group_id),
            user_id=str(event.user_id),
            is_private=False,
        )

    if not scope.enabled:
        return

    message_text = collect_message_text(event)
    if not message_text or not extract_douyin_urls(message_text):
        return

    if not config.douyin_cookie:
        # 对齐 douyin-downloader：无 Cookie 仅警告，仍尝试游客态解析
        logger.warning("抖音链接解析：未配置 Cookie，将继续尝试（失败率可能较高）")

    logger.info(
        "抖音链接解析：收到消息 user={} text={!r}",
        event.user_id,
        message_text[:120],
    )

    result = None
    try:
        result = await resolve_and_download(message_text, config.douyin_cookie)
        reply = build_douyin_link_message(result, config.message_templates)
        if isinstance(event, GroupMessageEvent):
            await bot.send_group_msg(group_id=event.group_id, message=reply)
        else:
            await bot.send_private_msg(user_id=event.user_id, message=reply)
        reply_scope = (
            f"group={event.group_id}"
            if isinstance(event, GroupMessageEvent)
            else "private"
        )
        logger.info(
            "已回复抖音链接解析: user={}, aweme_id={}, {}",
            event.user_id,
            result.aweme_id,
            reply_scope,
        )
    except DouyinResolveError as exc:
        logger.warning("抖音链接解析失败: {}", exc)
    except Exception:
        logger.opt(exception=True).error("抖音链接解析处理异常")
    finally:
        if result is not None:
            _cleanup_temp(result.file_path)


def _cleanup_temp(file_path: Path) -> None:
    try:
        parent = file_path.parent
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        # 仅清理我们创建的临时目录
        if parent.name.startswith("douyin_") and parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
    except Exception:
        logger.opt(exception=True).debug("清理抖音临时文件失败: {}", file_path)


@group_douyin_link_parser.handle()
async def handle_group_douyin_link(bot: Bot, event: GroupMessageEvent):
    await _handle_douyin_link_message(bot, event)


@private_douyin_link_parser.handle()
async def handle_private_douyin_link(bot: Bot, event: PrivateMessageEvent):
    await _handle_douyin_link_message(bot, event)


async def _on_config_reload(_snapshot) -> None:
    reload_config()
    config = get_config()
    logger.info(
        "抖音链接解析: 配置已热重载, Cookie={}",
        "已配置" if config.douyin_cookie else "未配置",
    )


def _register_config_reload() -> None:
    try:
        get_config_service().register_reload_callback(_on_config_reload)
    except Exception:
        logger.opt(exception=True).warning("抖音链接解析：配置热重载注册失败")


driver = get_driver()


@driver.on_startup
async def _douyin_link_parser_startup() -> None:
    _register_config_reload()
    config = get_config()
    logger.info("抖音链接解析插件已就绪")
    if not config.douyin_cookie:
        logger.warning(
            "抖音链接解析: 未配置 Cookie，将以游客态尝试；建议在设置中配置以提高成功率"
        )
