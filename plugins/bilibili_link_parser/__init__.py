"""
B 站链接自动解析插件

自动识别群聊/好友中的视频链接、直播间链接、b23.tv 短链与 QQ 小程序分享，
并回复封面、标题、UP 主/主播、时间信息与链接；可选下载并发送视频文件。
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11.message import Message
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.config.link_parser_policy import (
    LinkParserScopePolicy,
    resolve_link_parser_policy,
)
from shared.config.message_templates import LinkMessageTemplates
from shared.config.service import get_config_service
from shared.config.shared_media import (
    chmod_shared_media_file,
    ensure_shared_media_dir,
)
from utils.bilibili_api import (
    BilibiliVideoDownloadError,
    DynamicFetcher,
    VideoInfo,
    download_bilibili_video,
    extract_bilibili_refs,
    video_api_manager,
)
from utils.bilibili_api import api_manager as live_api_manager
from utils.screenshot import get_dynamic_screenshot

from .config import Config, get_config, reload_config
from .message_text import collect_message_text
from .sender import (
    build_dynamic_link_message,
    build_live_link_message,
    build_video_link_message,
)
from .video_send import all_sends_ok, send_batches, send_video_with_cover_fallback

__plugin_meta__ = PluginMetadata(
    name="B 站链接解析",
    description="自动解析群聊/好友中的 B 站视频、直播链接与 QQ 小程序分享",
    usage="发送含 BV 号、直播间链接、b23.tv 短链或 B 站 QQ 小程序分享即可触发",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

group_link_parser = on_message(priority=4, block=False)
private_link_parser = on_message(priority=4, block=False)

# ponytail: 流水线限临时文件占盘；编码/发送串行避免并发 ffmpeg + 同目录写冲突。
_PIPELINE_LIMIT = 2
_PIPELINE_SEM = asyncio.Semaphore(_PIPELINE_LIMIT)
_ENCODE_SEND_SEM = asyncio.Semaphore(1)


@dataclass
class _ResolvedReply:
    message: Message | None = None
    video: VideoInfo | None = None
    video_path: Path | None = None
    templates: LinkMessageTemplates | None = None


async def _fetch_dynamic_screenshot(
    dynamic,
    *,
    enabled: bool,
) -> bytes | None:
    if not enabled:
        return None
    screenshot_image, screenshot_error, page_url = await get_dynamic_screenshot(
        dynamic.id, is_article=dynamic.is_article
    )
    if screenshot_error:
        logger.warning("链接解析动态 {} 截图失败: {}", dynamic.id, screenshot_error)
    elif page_url and dynamic.url.startswith("https://t.bilibili.com/"):
        dynamic.url = page_url
    return screenshot_image


async def _maybe_download_video(
    video: VideoInfo,
    *,
    enabled: bool,
    cookie: str | None,
    output_dir: Path,
) -> Path | None:
    if not enabled:
        return None
    if not video.bvid or not video.cid:
        logger.warning(
            "B 站链接解析：缺少 bvid/cid，跳过视频发送 bvid={} cid={}",
            video.bvid,
            video.cid,
        )
        return None
    try:
        path = await download_bilibili_video(
            video_api_manager.api.session,
            bvid=video.bvid,
            cid=video.cid,
            cookie=cookie,
            output_dir=output_dir,
        )
        chmod_shared_media_file(path)
        return path
    except BilibiliVideoDownloadError as exc:
        logger.warning("B 站视频下载失败，降级为封面+文字: {}", exc)
        return None
    except Exception:
        logger.opt(exception=True).warning("B 站视频下载异常，降级为封面+文字")
        return None


async def _resolve_reply(
    config: Config,
    message_text: str,
    scope: LinkParserScopePolicy,
    *,
    enable_dynamic_screenshot: bool,
) -> _ResolvedReply:
    cookie = config.bilibili_cookie or None
    if not cookie:
        logger.warning("B 站链接解析：未配置 Cookie，直播接口可能返回 -352 或解析失败")

    media_dir = ensure_shared_media_dir(
        get_config_service().get_snapshot().link_parser_shared_media_dir
    )

    await video_api_manager.init(cookie)
    await live_api_manager.init(cookie)
    session = video_api_manager.api.session
    refs = await extract_bilibili_refs(message_text, session, cookie=cookie)
    if not refs:
        logger.debug("B 站链接解析：未识别到链接，text={!r}", message_text[:120])
        return _ResolvedReply()

    fetcher = DynamicFetcher(session, cookie)

    for ref in refs:
        try:
            if ref.kind == "video":
                if not scope.video_enabled:
                    continue
                video = await video_api_manager.get_video_detail(
                    bvid=ref.bvid, aid=ref.aid
                )
                if video:
                    video_path = await _maybe_download_video(
                        video,
                        enabled=scope.send_video_enabled,
                        cookie=cookie,
                        output_dir=media_dir,
                    )
                    if video_path is not None:
                        return _ResolvedReply(
                            video=video,
                            video_path=video_path,
                            templates=config.message_templates,
                        )
                    return _ResolvedReply(
                        message=build_video_link_message(
                            video, config.message_templates
                        )
                    )
            elif ref.kind == "dynamic" and ref.dynamic_id:
                if not scope.dynamic_enabled:
                    continue
                dynamic = await fetcher.fetch_dynamic_detail(
                    str(ref.dynamic_id),
                    cookie=cookie,
                    skip_live_dynamic=False,
                )
                if dynamic:
                    if dynamic.live_room_id and scope.live_enabled:
                        (
                            room_info,
                            user_info,
                        ) = await live_api_manager.get_room_and_user_info(
                            dynamic.live_room_id
                        )
                        if room_info:
                            return _ResolvedReply(
                                message=build_live_link_message(
                                    room_info, user_info, config.message_templates
                                )
                            )
                    screenshot_image = await _fetch_dynamic_screenshot(
                        dynamic, enabled=enable_dynamic_screenshot
                    )
                    return _ResolvedReply(
                        message=build_dynamic_link_message(
                            dynamic,
                            config.message_templates,
                            screenshot_image=screenshot_image,
                            include_dynamic_media=(
                                not enable_dynamic_screenshot
                                or screenshot_image is None
                            ),
                        )
                    )
            elif ref.room_id:
                if not scope.live_enabled:
                    continue
                room_info, user_info = await live_api_manager.get_room_and_user_info(
                    ref.room_id
                )
                if room_info:
                    return _ResolvedReply(
                        message=build_live_link_message(
                            room_info, user_info, config.message_templates
                        )
                    )
        except Exception:
            logger.opt(exception=True).warning("B 站链接解析失败 ref={}", ref)

    logger.warning("B 站链接解析：API 未返回有效内容 refs={}", refs)
    return _ResolvedReply()


def _message_id_of(send_result: object) -> object:
    if isinstance(send_result, dict):
        return send_result.get("message_id")
    return getattr(send_result, "message_id", send_result)


def _cleanup_temp(file_path: Path | None) -> None:
    """发送后删除视频文件；共享目录本身不删（仅清理偶然的 bilibili_* 临时目录）。"""
    if file_path is None:
        return
    try:
        parent = file_path.parent
        file_path.unlink(missing_ok=True)
        if parent.name.startswith("bilibili_") and parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
    except Exception:
        logger.opt(exception=True).debug("清理 B 站临时文件失败: {}", file_path)


async def _handle_link_message(
    bot: Bot, event: GroupMessageEvent | PrivateMessageEvent
) -> None:
    config = get_config()
    snap = get_config_service().get_snapshot()

    if isinstance(event, PrivateMessageEvent):
        scope = resolve_link_parser_policy(
            snap,
            user_id=str(event.user_id),
            is_private=True,
        )
    else:
        if str(event.user_id) == str(event.self_id):
            return
        scope = resolve_link_parser_policy(
            snap,
            group_id=str(event.group_id),
            user_id=str(event.user_id),
            is_private=False,
        )

    if not scope.video_enabled and not scope.live_enabled and not scope.dynamic_enabled:
        logger.info(
            "B 站链接解析: 策略未启用 user={} video={} live={} dynamic={} send_video={}",
            event.user_id,
            scope.video_enabled,
            scope.live_enabled,
            scope.dynamic_enabled,
            scope.send_video_enabled,
        )
        return

    message_text = collect_message_text(event)
    if not message_text:
        logger.debug("B 站链接解析：未提取到文本/链接 user={}", event.user_id)
        return

    logger.info(
        "B 站链接解析：收到消息 user={} text={!r}",
        event.user_id,
        message_text[:120],
    )

    # 仅在可能下载视频时占流水线名额；封面/文字路径保持轻量
    if scope.video_enabled and scope.send_video_enabled:
        if _PIPELINE_SEM.locked():
            logger.info("B 站链接解析：等待流水线名额 user={}", event.user_id)
        async with _PIPELINE_SEM:
            await _resolve_and_reply(
                bot,
                event,
                config,
                message_text,
                scope,
                enable_dynamic_screenshot=snap.dynamic_enable_screenshot,
            )
        return

    await _resolve_and_reply(
        bot,
        event,
        config,
        message_text,
        scope,
        enable_dynamic_screenshot=snap.dynamic_enable_screenshot,
    )


async def _resolve_and_reply(
    bot: Bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    config: Config,
    message_text: str,
    scope: LinkParserScopePolicy,
    *,
    enable_dynamic_screenshot: bool,
) -> None:
    resolved = _ResolvedReply()
    try:
        resolved = await _resolve_reply(
            config,
            message_text,
            scope,
            enable_dynamic_screenshot=enable_dynamic_screenshot,
        )
        templates = resolved.templates or config.message_templates
        if resolved.video is not None and resolved.video_path is not None:
            if _ENCODE_SEND_SEM.locked():
                logger.info(
                    "B 站链接解析：等待前序编码/发送完成 user={}", event.user_id
                )
            async with _ENCODE_SEND_SEM:
                send_results = await send_video_with_cover_fallback(
                    bot,
                    event,
                    video=resolved.video,
                    video_path=resolved.video_path,
                    templates=templates,
                )
        elif resolved.message is not None:
            send_results = await send_batches(bot, event, [resolved.message])
        else:
            return

        if not all_sends_ok(send_results):
            logger.warning(
                "B 站链接解析发送未确认成功 user={} results={!r}",
                event.user_id,
                send_results,
            )
            return

        reply_scope = (
            f"group={event.group_id}"
            if isinstance(event, GroupMessageEvent)
            else "private"
        )
        logger.info(
            "已回复 B 站链接解析: user={}, message_ids={}, {}",
            event.user_id,
            [_message_id_of(item) for item in send_results],
            reply_scope,
        )
    except ActionFailed as exc:
        detail = str(
            getattr(exc, "wording", None) or getattr(exc, "message", None) or exc
        )
        logger.warning(
            "B 站链接解析发送失败 user={} retcode={} detail={!r}",
            event.user_id,
            getattr(exc, "retcode", None),
            detail[:200],
        )
    except Exception:
        logger.opt(exception=True).error("发送 B 站链接解析结果失败")
    finally:
        _cleanup_temp(resolved.video_path)


@group_link_parser.handle()
async def handle_group_link(bot: Bot, event: GroupMessageEvent):
    await _handle_link_message(bot, event)


@private_link_parser.handle()
async def handle_private_link(bot: Bot, event: PrivateMessageEvent):
    await _handle_link_message(bot, event)


async def _on_config_reload(_snapshot) -> None:
    reload_config()
    config = get_config()
    logger.info(
        "B 站链接解析: 配置已热重载, Cookie={}",
        "已配置" if config.bilibili_cookie else "未配置",
    )


def _register_config_reload() -> None:
    try:
        from shared.config.service import get_config_service

        get_config_service().register_reload_callback(_on_config_reload)
    except Exception:
        logger.opt(exception=True).warning("B 站链接解析：配置热重载注册失败")


driver = get_driver()


@driver.on_startup
async def _link_parser_startup() -> None:
    _register_config_reload()
    config = get_config()
    logger.info("B 站链接解析插件已就绪")
    if not config.bilibili_cookie:
        logger.warning("B 站链接解析: 未登录 B 站，api接口可能返回 -352 或解析失败")
