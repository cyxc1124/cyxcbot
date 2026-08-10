"""X 推文消息发送模块。"""

from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.config.message_templates import XMessageTemplates
from shared.notify.at_all import X_AT_ALL_FALLBACK, resolve_at_all_prefix
from shared.notify.delivery import (
    DeliveryResult,
    TargetDelivery,
    empty_delivery_result,
)
from shared.notify.message_template import build_message_from_template
from utils.x_api import TweetItem
from utils.x_api.models import TweetMediaItem

SegmentPart = Union[MessageSegment, str]

_MEDIA_SEG_TYPES = frozenset({"video", "image"})
MAX_MEDIA_PER_MESSAGE = 10


class XSender:
    """X 推文消息发送器。"""

    def __init__(self, templates: Optional[XMessageTemplates] = None):
        self.templates = templates or XMessageTemplates()

    def build_tweet_message(self, tweet: TweetItem) -> Message:
        """严格按模板顺序构建推文推送消息。

        媒体须已下载到本地（file_path）；远程 URL 交给 OneBot 直连常因无代理失败。
        """
        text_variables = {
            "name": tweet.name or tweet.username,
            "username": tweet.username,
            "time": tweet.format_time(),
            "text": tweet.text or "",
            "url": tweet.url,
            "tweet_id": str(tweet.id),
        }

        return build_message_from_template(
            self.templates.push,
            text_variables,
            {"media": lambda: _media_parts(tweet)},
        )

    def _valid_bots(self) -> List[Tuple[str, Bot]]:
        return [
            (bot_id, bot)
            for bot_id, bot in get_driver().bots.items()
            if isinstance(bot, Bot)
        ]

    async def send_to_groups(
        self,
        message: Message,
        group_ids: List[str],
        *,
        at_all_enabled: bool = False,
    ) -> DeliveryResult:
        if not group_ids:
            return empty_delivery_result()

        batches = reply_batches(message)
        if not batches:
            batches = [message]

        valid_bots = self._valid_bots()
        if not valid_bots:
            return DeliveryResult(
                targets=[
                    TargetDelivery("group", group_id, False, "没有可用的机器人实例")
                    for group_id in group_ids
                ]
            )

        targets: List[TargetDelivery] = []
        for group_id in group_ids:
            delivery = TargetDelivery("group", group_id, False, "没有可用的机器人实例")
            for _, bot in valid_bots:
                delivery = await self._send_group_via_bot(
                    bot,
                    group_id,
                    batches,
                    at_all_enabled=at_all_enabled,
                )
                if delivery.success or _is_partial_sent(delivery):
                    break
            targets.append(delivery)
        return DeliveryResult(targets=targets)

    async def _send_group_via_bot(
        self,
        bot: Bot,
        group_id: str,
        batches: List[Message],
        *,
        at_all_enabled: bool = False,
    ) -> TargetDelivery:
        sent = 0
        try:
            prefix = Message()
            if at_all_enabled:
                prefix = await resolve_at_all_prefix(
                    bot,
                    group_id,
                    enabled=True,
                    fallback=X_AT_ALL_FALLBACK,
                )
            for index, batch in enumerate(batches):
                payload = prefix + batch if index == 0 and prefix else batch
                await bot.send_group_msg(group_id=int(group_id), message=payload)
                sent += 1
            logger.info("X 推文消息已发送到群组 {}", group_id)
            return TargetDelivery("group", group_id, True)
        except Exception as exc:
            if sent > 0:
                # 已有批次送达：视为成功，避免换 bot / 待重试整组导致重复推送。
                logger.opt(exception=True).error(
                    "发送消息到群组 {} 部分批次失败（已发 {}/{}），停止重试以免重复",
                    group_id,
                    sent,
                    len(batches),
                )
                return TargetDelivery(
                    "group",
                    group_id,
                    True,
                    f"partial_sent:{sent}/{len(batches)}:{exc}",
                )
            logger.opt(exception=True).error("发送消息到群组 {} 失败", group_id)
            return TargetDelivery("group", group_id, False, str(exc))

    async def send_to_users(
        self, message: Message, user_ids: List[str]
    ) -> DeliveryResult:
        if not user_ids:
            return empty_delivery_result()

        batches = reply_batches(message)
        if not batches:
            batches = [message]

        valid_bots = self._valid_bots()
        if not valid_bots:
            return DeliveryResult(
                targets=[
                    TargetDelivery("user", user_id, False, "没有可用的机器人实例")
                    for user_id in user_ids
                ]
            )

        targets: List[TargetDelivery] = []
        for user_id in user_ids:
            delivery = TargetDelivery("user", user_id, False, "没有可用的机器人实例")
            for _, bot in valid_bots:
                delivery = await self._send_user_via_bot(bot, user_id, batches)
                if delivery.success or _is_partial_sent(delivery):
                    break
            targets.append(delivery)
        return DeliveryResult(targets=targets)

    async def _send_user_via_bot(
        self, bot: Bot, user_id: str, batches: List[Message]
    ) -> TargetDelivery:
        sent = 0
        try:
            for batch in batches:
                await bot.send_private_msg(user_id=int(user_id), message=batch)
                sent += 1
            logger.info("X 推文消息已发送到好友 {}", user_id)
            return TargetDelivery("user", user_id, True)
        except Exception as exc:
            if sent > 0:
                logger.opt(exception=True).error(
                    "发送消息到好友 {} 部分批次失败（已发 {}/{}），停止重试以免重复",
                    user_id,
                    sent,
                    len(batches),
                )
                return TargetDelivery(
                    "user",
                    user_id,
                    True,
                    f"partial_sent:{sent}/{len(batches)}:{exc}",
                )
            logger.opt(exception=True).error("发送消息到好友 {} 失败", user_id)
            return TargetDelivery("user", user_id, False, str(exc))

    async def send_message(
        self,
        message: Message,
        group_ids: List[str],
        user_ids: List[str],
        *,
        at_all_enabled: bool = False,
    ) -> DeliveryResult:
        group_result = await self.send_to_groups(
            message, group_ids, at_all_enabled=at_all_enabled
        )
        user_result = await self.send_to_users(message, user_ids)
        return group_result.merge(user_result)


def _video_parts(file_path: Path) -> Iterable[SegmentPart]:
    if not file_path.exists():
        return []
    try:
        if file_path.stat().st_size <= 0:
            logger.warning("X 推送视频文件为空: {}", file_path)
            return []
        return [MessageSegment.video(file_path.resolve())]
    except Exception:
        logger.opt(exception=True).warning("添加推文视频失败: {}", file_path)
        return []


def _image_parts(file_path: Path) -> Iterable[SegmentPart]:
    if not file_path.exists():
        return []
    try:
        if file_path.stat().st_size <= 0:
            logger.warning("X 推送图片文件为空: {}", file_path)
            return []
        return [MessageSegment.image(file_path.resolve())]
    except Exception:
        logger.opt(exception=True).warning("添加推文图片失败: {}", file_path)
        return []


def _media_parts(tweet: TweetItem) -> Iterable[SegmentPart]:
    items: list[TweetMediaItem] = list(tweet.media_items or [])
    if not items and tweet.media_urls:
        items = [TweetMediaItem(kind="image", url=u) for u in tweet.media_urls]

    parts: List[SegmentPart] = []
    for item in items:
        if item.file_path is None:
            continue
        if item.kind == "video":
            parts.extend(_video_parts(item.file_path))
        else:
            parts.extend(_image_parts(item.file_path))
    return parts


def _chunk_media(media: Message, *, size: int = MAX_MEDIA_PER_MESSAGE) -> list[Message]:
    chunks: list[Message] = []
    current = Message()
    count = 0
    for seg in media:
        if count >= size:
            chunks.append(current)
            current = Message()
            count = 0
        current.append(seg)
        count += 1
    if current:
        chunks.append(current)
    return chunks


def reply_batches(message: Message) -> list[Message]:
    """按模板顺序拆批：保留 leading 文案 → 媒体 → trailing 文案。

    纯图且数量未超限时整条原样发送，避免打乱 ``{text}{media}{url}`` 顺序。
    含视频或图片过多时必须拆条（QQ 不能 video↔text 混排 / 同条图片过多）。
    """
    if not message:
        return []

    has_video = any(seg.type == "video" for seg in message)
    media_count = sum(1 for seg in message if seg.type in _MEDIA_SEG_TYPES)
    if not has_video and media_count <= MAX_MEDIA_PER_MESSAGE:
        return [message]

    leading = Message()
    media = Message()
    trailing = Message()
    seen_media = False
    for seg in message:
        if seg.type in _MEDIA_SEG_TYPES:
            seen_media = True
            media.append(seg)
        elif seg.type == "text" and not str(seg.data.get("text", "")).strip():
            continue
        elif not seen_media:
            leading.append(seg)
        else:
            trailing.append(seg)

    batches: list[Message] = []
    if leading:
        batches.append(leading)
    if media:
        batches.extend(_chunk_media(media))
    if trailing:
        batches.append(trailing)
    return batches


def _is_partial_sent(delivery: TargetDelivery) -> bool:
    return bool(delivery.error and str(delivery.error).startswith("partial_sent:"))
