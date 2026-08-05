"""
抖音链接自动解析插件

识别群聊/好友中的抖音分享链接，下载视频/图集/Live 图并回传。
Live 图以视频消息发送。
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
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
from .send_result import is_onebot_send_success
from .sender import build_douyin_link_message, reply_batches

__plugin_meta__ = PluginMetadata(
    name="抖音链接解析",
    description="自动解析群聊/好友中的抖音分享链接并回传视频/图集/Live 图",
    usage="发送含抖音短链或作品链接即可触发",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

group_douyin_link_parser = on_message(priority=4, block=False)
private_douyin_link_parser = on_message(priority=4, block=False)

# ponytail: 流水线准入限制临时文件占盘（下载可并行到上限）；编码/发送另串行化
# 控 base64 内存。CDN 慢只占准入名额，不拖死已下完的发送。升级：共享卷 file://。
_PIPELINE_LIMIT = 2
_PIPELINE_SEM = asyncio.Semaphore(_PIPELINE_LIMIT)
_ENCODE_SEND_SEM = asyncio.Semaphore(1)


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

    if _PIPELINE_SEM.locked():
        logger.info("抖音链接解析：等待流水线名额 user={}", event.user_id)

    async with _PIPELINE_SEM:
        await _download_and_reply(bot, event, config, message_text)


async def _download_and_reply(
    bot: Bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    config: Config,
    message_text: str,
) -> None:
    result = None
    try:
        # CDN 可能长时间超时；不放在编码锁内（仍占流水线名额，限制临时文件数）
        result = await resolve_and_download(message_text, config.douyin_cookie)
        if _ENCODE_SEND_SEM.locked():
            logger.info("抖音链接解析：等待前序编码/发送完成 user={}", event.user_id)
        async with _ENCODE_SEND_SEM:
            # read_bytes + f2s(base64) 是同步 CPU/IO，挪出事件循环
            reply = await asyncio.to_thread(
                build_douyin_link_message, result, config.message_templates
            )
            # 含 video 时拆成媒体 + 文案两条：同条混排时 QQ 常只显示视频
            batches = reply_batches(reply)
            send_results: list[object] = []
            for batch in batches:
                if isinstance(event, GroupMessageEvent):
                    send_results.append(
                        await bot.send_group_msg(group_id=event.group_id, message=batch)
                    )
                else:
                    send_results.append(
                        await bot.send_private_msg(user_id=event.user_id, message=batch)
                    )

        if not send_results or not all(
            is_onebot_send_success(item) for item in send_results
        ):
            logger.warning(
                "抖音链接解析发送未确认成功 user={} aweme_id={} results={!r}",
                event.user_id,
                result.aweme_id,
                send_results,
            )
            return

        reply_scope = (
            f"group={event.group_id}"
            if isinstance(event, GroupMessageEvent)
            else "private"
        )
        logger.info(
            "已回复抖音链接解析: user={}, aweme_id={}, message_ids={}, {}",
            event.user_id,
            result.aweme_id,
            [_message_id_of(item) for item in send_results],
            reply_scope,
        )
    except DouyinResolveError as exc:
        logger.warning("抖音链接解析失败: {}", exc)
    except ActionFailed as exc:
        # NapCat 常把整段 invoke payload 塞进 message，避免 ERROR 刷屏
        detail = str(
            getattr(exc, "wording", None) or getattr(exc, "message", None) or exc
        )
        logger.warning(
            "抖音链接解析发送失败 user={} aweme_id={} retcode={} detail={!r}",
            event.user_id,
            getattr(result, "aweme_id", None),
            getattr(exc, "retcode", None),
            detail[:200],
        )
    except Exception:
        logger.opt(exception=True).error("抖音链接解析处理异常")
    finally:
        # send_* 返回有效 message_id 表示协议端已接受，可立即清理；
        # 失败路径同样清理，避免临时目录泄漏。
        if result is not None:
            _cleanup_temp(result.file_path)


def _message_id_of(send_result: object) -> object:
    if isinstance(send_result, dict):
        return send_result.get("message_id")
    return getattr(send_result, "message_id", send_result)


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
