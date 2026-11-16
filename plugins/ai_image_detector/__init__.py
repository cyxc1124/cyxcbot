"""Reply to a quoted image with a configurable trigger to inspect its provenance."""

import asyncio

import aiohttp
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

from shared.adapter.inbound import is_group_event, is_tome, plaintext_of
from shared.adapter.outbound import send_event_message
from shared.config.ai_image import VisionProviderRecord
from shared.config.command_aliases import (
    CommandAliasEntry,
    command_aliases_for_event,
    match_plain,
    resolve_entry,
)
from shared.config.service import get_config_service
from shared.config.types import AppConfigSnapshot
from utils.vision_api import (
    VisionAPIError,
    VisionImage,
    judge_image,
    prepare_vision_image,
)

from .c2pa_check import inspect_c2pa
from .image import ImageDetectionError, download_image, image_media_type
from .openai_check import check_openai
from .report import VisionResult, build_report

__plugin_meta__ = PluginMetadata(
    name="AI 图片检测",
    description="引用图片检查 C2PA 凭证与 OpenAI SynthID 水印，可接入多个视觉模型共同判断",
    usage="引用一张图片发送触发词（默认 ai吗？，可在 Web Admin → AI 图片检测 → 触发命令 修改）",
    type="application",
    supported_adapters={"~onebot.v11"},
)

COMMAND_ID = "ai_image_detect"
_detection_lock = asyncio.Lock()


async def is_ai_image_command(bot: Bot, event: MessageEvent) -> bool:
    aliases = await command_aliases_for_event(
        get_config_service().get_snapshot(), bot, event
    )
    entry = aliases.get(COMMAND_ID)
    if entry is None or not entry.enabled:
        return False
    # 触发词不区分英文大小写，保留 ai吗 / AI吗 / Ai吗 都能触发的习惯。
    folded = {
        **aliases,
        COMMAND_ID: CommandAliasEntry(
            enabled=True, triggers=[trigger.casefold() for trigger in entry.triggers]
        ),
    }
    return match_plain(
        plaintext_of(event).casefold(),
        COMMAND_ID,
        folded,
        is_tome=is_group_event(event) and is_tome(event),
    )


ai_image_command = on_message(rule=Rule(is_ai_image_command), priority=5, block=True)


async def _openai_outcome(
    data: bytes, media_type: str, snapshot: AppConfigSnapshot, kinds: frozenset[str]
) -> tuple[dict[str, dict] | None, str]:
    key = snapshot.ai_image_openai_api_key
    if not kinds or not key:
        return None, ""
    try:
        return (
            await check_openai(
                data, media_type, key, proxy=snapshot.ai_image_openai_proxy
            ),
            "",
        )
    except ImageDetectionError as exc:
        return None, str(exc)
    except Exception as exc:
        logger.opt(exception=RuntimeError(type(exc).__name__)).error(
            "OpenAI 图片来源检测失败"
        )
        return None, "OpenAI 检测失败，外部检测未完成。"


async def _vision_outcome(
    provider: VisionProviderRecord, image: VisionImage, snapshot: AppConfigSnapshot
) -> VisionResult:
    try:
        verdict = await judge_image(
            provider, image, proxy=snapshot.proxy(provider.proxy_id)
        )
    except VisionAPIError as exc:
        return VisionResult(provider.name, error=exc.message)
    except Exception as exc:
        logger.opt(exception=RuntimeError(type(exc).__name__)).error(
            "视觉模型「{}」检测失败", provider.name
        )
        return VisionResult(provider.name, error="检测失败，本次未完成。")
    return VisionResult(
        provider.name, verdict.verdict, verdict.confidence, verdict.reason
    )


async def _vision_outcomes(
    data: bytes, providers: list[VisionProviderRecord], snapshot: AppConfigSnapshot
) -> list[VisionResult]:
    if not providers:
        return []
    try:
        # 只编码一次，所有供应商共用同一份 base64。
        image = await asyncio.to_thread(prepare_vision_image, data)
    except VisionAPIError as exc:
        return [
            VisionResult(provider.name, error=exc.message) for provider in providers
        ]
    return list(
        await asyncio.gather(
            *(_vision_outcome(provider, image, snapshot) for provider in providers)
        )
    )


async def detect_quoted_image(bot: Bot, event: MessageEvent) -> str:
    snapshot = get_config_service().get_snapshot()
    openai_kinds = frozenset(
        kind
        for kind, enabled in (
            ("c2pa", snapshot.ai_image_openai_c2pa_enabled),
            ("synthid", snapshot.ai_image_openai_synthid_enabled),
        )
        if enabled
    )
    providers = [
        provider for provider in snapshot.ai_image_vision_providers if provider.enabled
    ]
    if not (snapshot.ai_image_local_c2pa_enabled or openai_kinds or providers):
        return "管理员尚未启用任何图片检测方式。"
    images = event.reply.message["image"] if event.reply else []
    if len(images) != 1:
        trigger = next(
            iter(resolve_entry(COMMAND_ID, snapshot.command_aliases).triggers), "ai吗？"
        )
        return f"请引用一条只包含一张图片的消息，回复「{trigger}」。"
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
    local = (
        await asyncio.to_thread(inspect_c2pa, data)
        if snapshot.ai_image_local_c2pa_enabled
        else None
    )
    (remote, remote_error), vision = await asyncio.gather(
        _openai_outcome(data, media_type, snapshot, openai_kinds),
        _vision_outcomes(data, providers, snapshot),
    )
    return build_report(
        local, remote, remote_error, openai_kinds=openai_kinds, vision=vision
    )


@ai_image_command.handle()
async def handle_ai_image(bot: Bot, event: MessageEvent) -> None:
    reply = MessageSegment.reply(
        event.reply.message_id if event.reply else event.message_id
    )
    if _detection_lock.locked():
        await send_event_message(
            bot, event, reply + MessageSegment.text("图片检测正在进行，请稍后再试。")
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
        await send_event_message(bot, event, reply + MessageSegment.text(text))
