"""X 推文消息发送模块。"""

from hashlib import sha256
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.adapter.bots import iter_onebot_bots, messaging_bots
from shared.adapter.ids import is_numeric_qq_id
from shared.adapter.outbound import convert_onebot_message, send_group, send_user
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.message_templates import XMessageTemplates
from shared.notify.at_all import X_AT_ALL_FALLBACK, resolve_at_all_prefix
from shared.notify.delivery import (
    DeliveryProgressCallback,
    DeliveryResult,
    TargetDelivery,
    empty_delivery_result,
)
from shared.notify.message_template import build_message_from_template
from utils.x_api import TweetItem
from utils.x_api.models import TweetMediaItem

from .delivery_retry import (
    batch_plan_fingerprint,
    normalize_batch_start,
)

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

    def plan_fingerprint(
        self,
        message: Message,
        *,
        at_all_enabled: bool = False,
        expected_fingerprint: str = "",
    ) -> str:
        batches = reply_batches(message) or ([message] if message else [])
        return _plan_fingerprint(
            batches, at_all_enabled=at_all_enabled, expected=expected_fingerprint
        )

    async def send_to_groups(
        self,
        message: Message,
        group_ids: List[str],
        *,
        at_all_enabled: bool = False,
        start_by_target: Optional[Dict[str, int]] = None,
        expected_fingerprint: str = "",
        on_progress: DeliveryProgressCallback | None = None,
    ) -> DeliveryResult:
        if not group_ids:
            return empty_delivery_result()

        batches = reply_batches(message)
        if not batches:
            batches = [message]
        expected_fp = (expected_fingerprint or "").strip()
        plan_fp = _plan_fingerprint(
            batches, at_all_enabled=at_all_enabled, expected=expected_fp
        )

        starts = start_by_target or {}
        if not messaging_bots():
            return DeliveryResult(
                targets=[
                    TargetDelivery(
                        "group",
                        group_id,
                        False,
                        f"resume_from:{max(0, int(starts.get(group_id, 0) or 0))}:"
                        f"没有可用的机器人实例",
                    )
                    for group_id in group_ids
                ]
            )

        targets: List[TargetDelivery] = []
        for group_id in group_ids:
            start = max(0, int(starts.get(group_id, 0) or 0))
            targets.append(
                await self._send_group_batches(
                    group_id,
                    batches,
                    start=start,
                    at_all_enabled=at_all_enabled,
                    expected_fingerprint=expected_fp,
                    actual_fingerprint=plan_fp,
                    on_progress=on_progress,
                )
            )
        return DeliveryResult(targets=targets)

    async def _send_group_batches(
        self,
        group_id: str,
        batches: List[Message],
        *,
        start: int = 0,
        at_all_enabled: bool = False,
        expected_fingerprint: str = "",
        actual_fingerprint: str = "",
        on_progress: DeliveryProgressCallback | None = None,
    ) -> TargetDelivery:
        prepared: list[Message] = list(batches)
        if at_all_enabled:
            prefix = Message(f"{X_AT_ALL_FALLBACK} ")
            if is_numeric_qq_id(group_id):
                onebot_bots = iter_onebot_bots()
                if onebot_bots:
                    prefix = await resolve_at_all_prefix(
                        onebot_bots[0],
                        group_id,
                        enabled=True,
                        fallback=X_AT_ALL_FALLBACK,
                    )
            prepared = [prefix, *batches]
        if not is_numeric_qq_id(group_id):
            return await self._send_official_batches(
                group_id,
                "group",
                prepared,
                start=start,
                expected_fingerprint=expected_fingerprint,
                actual_fingerprint=actual_fingerprint,
                on_progress=on_progress,
            )
        ok, start, stale_error = normalize_batch_start(
            start,
            len(prepared),
            expected_fingerprint=expected_fingerprint,
            actual_fingerprint=actual_fingerprint,
        )
        if not ok:
            logger.warning(
                "群组 {} 续传计划失效（{}），保留 pending 待重试",
                group_id,
                stale_error,
            )
            return TargetDelivery("group", group_id, False, stale_error)
        sent = start
        try:
            for index in range(start, len(prepared)):
                await send_group(group_id, prepared[index])
                sent = index + 1
                if on_progress is not None:
                    await on_progress("group", group_id, sent)
            logger.info("X 推文消息已发送到群组 {}", group_id)
            return TargetDelivery("group", group_id, True)
        except LoggedQQApiError as exc:
            return TargetDelivery("group", group_id, False, f"resume_from:{sent}:{exc}")
        except Exception as exc:
            logger.opt(exception=True).error(
                "发送消息到群组 {} 失败（已发 {}/{}）",
                group_id,
                sent,
                len(prepared),
            )
            return TargetDelivery("group", group_id, False, f"resume_from:{sent}:{exc}")

    async def send_to_users(
        self,
        message: Message,
        user_ids: List[str],
        *,
        start_by_target: Optional[Dict[str, int]] = None,
        expected_fingerprint: str = "",
        at_all_enabled: bool = False,
        on_progress: DeliveryProgressCallback | None = None,
    ) -> DeliveryResult:
        if not user_ids:
            return empty_delivery_result()

        batches = reply_batches(message)
        if not batches:
            batches = [message]
        expected_fp = (expected_fingerprint or "").strip()
        plan_fp = _plan_fingerprint(
            batches, at_all_enabled=at_all_enabled, expected=expected_fp
        )

        starts = start_by_target or {}
        if not messaging_bots():
            return DeliveryResult(
                targets=[
                    TargetDelivery(
                        "user",
                        user_id,
                        False,
                        f"resume_from:{max(0, int(starts.get(user_id, 0) or 0))}:"
                        f"没有可用的机器人实例",
                    )
                    for user_id in user_ids
                ]
            )

        targets: List[TargetDelivery] = []
        for user_id in user_ids:
            start = max(0, int(starts.get(user_id, 0) or 0))
            targets.append(
                await self._send_user_batches(
                    user_id,
                    batches,
                    start=start,
                    expected_fingerprint=expected_fp,
                    actual_fingerprint=plan_fp,
                    on_progress=on_progress,
                )
            )
        return DeliveryResult(targets=targets)

    async def _send_user_batches(
        self,
        user_id: str,
        batches: List[Message],
        *,
        start: int = 0,
        expected_fingerprint: str = "",
        actual_fingerprint: str = "",
        on_progress: DeliveryProgressCallback | None = None,
    ) -> TargetDelivery:
        if not is_numeric_qq_id(user_id):
            return await self._send_official_batches(
                user_id,
                "user",
                batches,
                start=start,
                expected_fingerprint=expected_fingerprint,
                actual_fingerprint=actual_fingerprint,
                on_progress=on_progress,
            )
        ok, start, stale_error = normalize_batch_start(
            start,
            len(batches),
            expected_fingerprint=expected_fingerprint,
            actual_fingerprint=actual_fingerprint,
        )
        if not ok:
            logger.warning(
                "好友 {} 续传计划失效（{}），保留 pending 待重试",
                user_id,
                stale_error,
            )
            return TargetDelivery("user", user_id, False, stale_error)
        sent = start
        try:
            for index in range(start, len(batches)):
                await send_user(user_id, batches[index])
                sent = index + 1
                if on_progress is not None:
                    await on_progress("user", user_id, sent)
            logger.info("X 推文消息已发送到好友 {}", user_id)
            return TargetDelivery("user", user_id, True)
        except LoggedQQApiError as exc:
            return TargetDelivery("user", user_id, False, f"resume_from:{sent}:{exc}")
        except Exception as exc:
            logger.opt(exception=True).error(
                "发送消息到好友 {} 失败（已发 {}/{}）",
                user_id,
                sent,
                len(batches),
            )
            return TargetDelivery("user", user_id, False, f"resume_from:{sent}:{exc}")

    async def _send_official_batches(
        self,
        target_id: str,
        target_type: str,
        batches: List[Message],
        *,
        start: int,
        expected_fingerprint: str,
        actual_fingerprint: str,
        on_progress: DeliveryProgressCallback | None,
    ) -> TargetDelivery:
        message = Message([segment for batch in batches for segment in batch])
        part_count = len(convert_onebot_message(message))
        ok, start, error = normalize_batch_start(
            start,
            part_count,
            expected_fingerprint=expected_fingerprint,
            actual_fingerprint=actual_fingerprint,
        )
        if not ok:
            return TargetDelivery(target_type, target_id, False, error)
        sent = start

        async def checkpoint(next_part: int) -> None:
            nonlocal sent
            sent = next_part
            if on_progress is not None:
                await on_progress(target_type, target_id, next_part)

        try:
            if start < part_count:
                send = send_group if target_type == "group" else send_user
                await send(target_id, message, start=start, on_part_sent=checkpoint)
            logger.info("X 推文消息已发送到官方会话 {}", target_id)
            return TargetDelivery(target_type, target_id, True)
        except LoggedQQApiError as exc:
            return TargetDelivery(
                target_type, target_id, False, f"resume_from:{sent}:{exc}"
            )
        except Exception as exc:
            logger.opt(exception=True).error("发送 X 消息到官方会话 {} 失败", target_id)
            return TargetDelivery(
                target_type, target_id, False, f"resume_from:{sent}:{exc}"
            )

    async def send_message(
        self,
        message: Message,
        group_ids: List[str],
        user_ids: List[str],
        *,
        at_all_enabled: bool = False,
        group_starts: Optional[Dict[str, int]] = None,
        user_starts: Optional[Dict[str, int]] = None,
        expected_fingerprint: str = "",
        on_progress: DeliveryProgressCallback | None = None,
    ) -> DeliveryResult:
        group_result = await self.send_to_groups(
            message,
            group_ids,
            at_all_enabled=at_all_enabled,
            start_by_target=group_starts,
            expected_fingerprint=expected_fingerprint,
            on_progress=on_progress,
        )
        user_result = await self.send_to_users(
            message,
            user_ids,
            start_by_target=user_starts,
            expected_fingerprint=expected_fingerprint,
            at_all_enabled=at_all_enabled,
            on_progress=on_progress,
        )
        return group_result.merge(user_result)


def _plan_fingerprint(
    batches: List[Message], *, at_all_enabled: bool, expected: str = ""
) -> str:
    legacy = batch_plan_fingerprint([_batch_kind_key(batch) for batch in batches])
    # 升级前的 pending 仍按旧指纹续传；新进度同时校验群前缀策略。
    if expected and not expected.startswith("v2:"):
        return legacy
    return "v2:" + sha256(f"{at_all_enabled}:{legacy}".encode()).hexdigest()


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


def _text_image_batches(non_video: Message) -> list[Message]:
    """文字 + 图片可同条（对齐抖音图集）；图片过多再拆。"""
    if not non_video:
        return []
    image_count = sum(1 for seg in non_video if seg.type == "image")
    if image_count <= MAX_MEDIA_PER_MESSAGE:
        return [non_video]

    images = Message([seg for seg in non_video if seg.type == "image"])
    caption = Message([seg for seg in non_video if seg.type != "image"])
    chunks = _chunk_media(images)
    if not caption:
        return chunks
    first_image = next(
        (i for i, seg in enumerate(non_video) if seg.type == "image"), None
    )
    first_caption = next(
        (i for i, seg in enumerate(non_video) if seg.type != "image"), None
    )
    if (
        first_caption is not None
        and first_image is not None
        and first_caption < first_image
    ):
        return [caption, *chunks]
    return [*chunks, caption]


def reply_batches(message: Message) -> list[Message]:
    """对齐抖音：视频必须单独发；文字与图片可同条。

    单次扫描保序：遇到视频先冲刷已有文字/图，再发该视频批，避免
    ``video, image, video`` 被重排成 ``video, video, image``。
    """
    if not message:
        return []

    batches: list[Message] = []
    pending = Message()

    def flush_pending() -> None:
        nonlocal pending
        if pending:
            batches.extend(_text_image_batches(pending))
            pending = Message()

    for seg in message:
        if seg.type == "video":
            flush_pending()
            batches.append(Message([seg]))
            continue
        if seg.type == "text" and not str(seg.data.get("text", "")).strip():
            continue
        pending.append(seg)
    flush_pending()
    return batches


def _batch_kind_key(batch: Message) -> str:
    kinds: list[str] = []
    for seg in batch:
        if seg.type == "video":
            kinds.append("v")
        elif seg.type == "image":
            kinds.append("i")
        elif seg.type == "text":
            kinds.append("t")
        else:
            kinds.append("x")
    return "".join(kinds) or "e"
