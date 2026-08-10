"""
X (Twitter) 链接自动解析插件

识别群聊/好友中的 x.com / twitter.com / t.co 链接，拉取推文并以文字+图片/视频回传。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.config.service import get_config_service
from shared.config.shared_media import chmod_shared_media_file, ensure_shared_media_dir
from shared.config.x_link_parser_policy import resolve_x_link_parser_policy
from utils.x_api import XApiClient, create_session, extract_x_tweet_ids, extract_x_urls
from utils.x_api.download import cleanup_media_files, materialize_tweet_media

from .config import Config, get_config, reload_config
from .message_text import collect_message_text
from .send_result import is_onebot_send_success
from .sender import build_x_link_message, reply_batches

__plugin_meta__ = PluginMetadata(
    name="X 链接解析",
    description="自动解析群聊/好友中的 X (Twitter) 链接并回传推文文字、图片与视频",
    usage="发送含 x.com / twitter.com / t.co 链接即可触发",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

group_x_link_parser = on_message(priority=4, block=False)
private_x_link_parser = on_message(priority=4, block=False)

# ponytail: 限制并发解析，避免刷屏时打爆 X API 配额；发送另串行化。
_PIPELINE_LIMIT = 2
_PIPELINE_SEM = asyncio.Semaphore(_PIPELINE_LIMIT)
_SEND_SEM = asyncio.Semaphore(1)


async def _handle_x_link_message(
    bot: Bot, event: GroupMessageEvent | PrivateMessageEvent
) -> None:
    config = get_config()
    snap = get_config_service().get_snapshot()

    if isinstance(event, PrivateMessageEvent):
        scope = resolve_x_link_parser_policy(
            snap,
            user_id=str(event.user_id),
            is_private=True,
        )
    else:
        if str(event.user_id) == str(event.self_id):
            return
        scope = resolve_x_link_parser_policy(
            snap,
            group_id=str(event.group_id),
            user_id=str(event.user_id),
            is_private=False,
        )

    if not scope.enabled:
        return

    message_text = collect_message_text(event)
    if not message_text or not extract_x_urls(message_text):
        return

    if not config.x_api_bearer:
        logger.warning("X 链接解析：未配置 Bearer Token，跳过")
        return

    logger.info(
        "X 链接解析：收到消息 user={} text={!r}",
        event.user_id,
        message_text[:120],
    )

    if _PIPELINE_SEM.locked():
        logger.info("X 链接解析：等待流水线名额 user={}", event.user_id)

    async with _PIPELINE_SEM:
        await _fetch_and_reply(bot, event, config, message_text)


async def _fetch_and_reply(
    bot: Bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    config: Config,
    message_text: str,
) -> None:
    session = create_session(config.x_proxy)
    client = XApiClient(session, config.x_api_bearer)
    downloaded: list[Path] = []
    try:
        tweet_ids = await extract_x_tweet_ids(message_text, session)
        if not tweet_ids:
            logger.debug("X 链接解析：未解析到推文 ID user={}", event.user_id)
            return

        media_dir = ensure_shared_media_dir(
            get_config_service().get_snapshot().link_parser_shared_media_dir
        )

        for tweet_id in tweet_ids:
            tweet = await client.get_tweet_by_id(tweet_id)
            if tweet is None:
                logger.warning("X 链接解析：拉取推文失败 tweet_id={}", tweet_id)
                continue

            # CDN 可能较慢；下载不占发送锁（仍占流水线名额）。
            paths = await materialize_tweet_media(session, tweet, media_dir)
            for path in paths:
                chmod_shared_media_file(path)
            downloaded.extend(paths)

            if _SEND_SEM.locked():
                logger.info("X 链接解析：等待前序发送完成 user={}", event.user_id)
            async with _SEND_SEM:
                reply = build_x_link_message(tweet, config.message_templates)
                batches = reply_batches(reply)
                send_results: list[object] = []
                for batch in batches:
                    if isinstance(event, GroupMessageEvent):
                        send_results.append(
                            await bot.send_group_msg(
                                group_id=event.group_id, message=batch
                            )
                        )
                    else:
                        send_results.append(
                            await bot.send_private_msg(
                                user_id=event.user_id, message=batch
                            )
                        )

            if not send_results or not all(
                is_onebot_send_success(item) for item in send_results
            ):
                logger.warning(
                    "X 链接解析发送未确认成功 user={} tweet_id={} results={!r}",
                    event.user_id,
                    tweet_id,
                    send_results,
                )
                continue

            reply_scope = (
                f"group={event.group_id}"
                if isinstance(event, GroupMessageEvent)
                else "private"
            )
            logger.info(
                "已回复 X 链接解析: user={}, tweet_id={}, message_ids={}, {}",
                event.user_id,
                tweet_id,
                [_message_id_of(item) for item in send_results],
                reply_scope,
            )
    except ActionFailed as exc:
        detail = str(
            getattr(exc, "wording", None) or getattr(exc, "message", None) or exc
        )
        logger.warning(
            "X 链接解析发送失败 user={} retcode={} detail={!r}",
            event.user_id,
            getattr(exc, "retcode", None),
            detail[:200],
        )
    except Exception:
        logger.opt(exception=True).error("X 链接解析处理异常")
    finally:
        cleanup_media_files(downloaded)
        await session.close()


def _message_id_of(send_result: object) -> object:
    if isinstance(send_result, dict):
        return send_result.get("message_id")
    return getattr(send_result, "message_id", send_result)


@group_x_link_parser.handle()
async def handle_group_x_link(bot: Bot, event: GroupMessageEvent):
    await _handle_x_link_message(bot, event)


@private_x_link_parser.handle()
async def handle_private_x_link(bot: Bot, event: PrivateMessageEvent):
    await _handle_x_link_message(bot, event)


async def _on_config_reload(_snapshot) -> None:
    reload_config()
    config = get_config()
    logger.info(
        "X 链接解析: 配置已热重载, Bearer={}",
        "已配置" if config.x_api_bearer else "未配置",
    )


def _register_config_reload() -> None:
    try:
        get_config_service().register_reload_callback(_on_config_reload)
    except Exception:
        logger.opt(exception=True).warning("X 链接解析：配置热重载注册失败")


driver = get_driver()


@driver.on_startup
async def _x_link_parser_startup() -> None:
    _register_config_reload()
    config = get_config()
    logger.info("X 链接解析插件已就绪")
    if not config.x_api_bearer:
        logger.warning("X 链接解析: 未配置 Bearer Token；请在设置 → X 账号中配置")
