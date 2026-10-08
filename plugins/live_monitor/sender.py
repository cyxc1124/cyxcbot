"""
直播通知消息发送模块
负责构建和发送直播开播/关播通知消息
参考 stream_notify 的推送方式实现
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from typing import Iterable, List, Optional, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.log import logger

from shared.adapter.bots import messaging_bots
from shared.adapter.outbound import send_group, send_user
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.message_templates import LiveMessageTemplates
from shared.notify.at_all import LIVE_AT_ALL_FALLBACK
from shared.notify.delivery import (
    DeliveryProgressCallback,
    DeliveryResult,
    PendingDelivery,
    TargetDelivery,
    empty_delivery_result,
)
from shared.notify.message_template import build_message_from_template, safe_text
from utils.bilibili_api import RoomInfo, UserInfo

from .card_generator import PrefetchImages

SegmentPart = Union[MessageSegment, str]


class LiveNotificationSender:
    """直播通知发送器"""

    def __init__(
        self,
        include_room_info: bool = True,
        templates: Optional[LiveMessageTemplates] = None,
    ):
        self.include_room_info = include_room_info
        self.templates = templates or LiveMessageTemplates()

    def template_uses_card(self, status: str) -> bool:
        """模板是否包含 {card} 占位符。"""
        template = self.templates.start if status == "start" else self.templates.end
        return "{card}" in template

    def build_start_message(
        self,
        streamer_name: str,
        room_info: Optional[RoomInfo],
        card_image: Optional[bytes] = None,
        *,
        at_all_enabled: bool = False,
        can_at_all: bool = False,
    ) -> Message:
        """严格按模板顺序构建开播通知消息。"""
        message = Message()

        if at_all_enabled:
            if can_at_all:
                message.append(MessageSegment.at("all"))
            else:
                message.append(safe_text(LIVE_AT_ALL_FALLBACK))
            message.append(safe_text(" "))

        text_variables = self._start_text_variables(streamer_name, room_info)

        def card_parts() -> Iterable[SegmentPart]:
            if not card_image:
                return []
            try:
                return [MessageSegment.image(card_image)]
            except Exception as exc:
                logger.warning("添加卡片图片到消息失败: {}", exc)
                return []

        def cover_parts() -> Iterable[SegmentPart]:
            if card_image or not room_info or not room_info.cover:
                return []
            try:
                return [MessageSegment.image(room_info.cover)]
            except Exception as exc:
                logger.warning("添加直播封面失败: {}", exc)
                return []

        body = build_message_from_template(
            self.templates.start,
            text_variables,
            {"card": card_parts, "cover": cover_parts},
        )
        return message + body

    def build_end_message(
        self,
        streamer_name: str,
        card_image: Optional[bytes] = None,
        duration_seconds: int = 0,
    ) -> Message:
        """严格按模板顺序构建下播通知消息。"""
        duration_str = (
            self._format_duration(duration_seconds) if duration_seconds > 0 else ""
        )
        text_variables = {
            "streamer_name": streamer_name,
            "duration": duration_str,
        }

        def card_parts() -> Iterable[SegmentPart]:
            if not card_image:
                return []
            try:
                return [MessageSegment.image(card_image)]
            except Exception as exc:
                logger.warning("添加下播卡片图片到消息失败: {}", exc)
                return []

        return build_message_from_template(
            self.templates.end,
            text_variables,
            {"card": card_parts},
        )

    def _start_text_variables(
        self,
        streamer_name: str,
        room_info: Optional[RoomInfo],
    ) -> dict[str, str]:
        variables = {"streamer_name": streamer_name, "title": "", "time": "", "url": ""}
        if not self.include_room_info or not room_info:
            return variables

        variables["title"] = room_info.title
        variables["url"] = room_info.get_live_url()
        if room_info.live_start_time > 0:
            start_time = datetime.fromtimestamp(room_info.live_start_time)
            variables["time"] = start_time.strftime("%Y-%m-%d %H:%M:%S")
        return variables

    def _format_duration(self, seconds: int) -> str:
        if seconds <= 0:
            return ""

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}小时{minutes}分钟{secs}秒"
        if minutes > 0:
            return f"{minutes}分钟{secs}秒"
        return f"{secs}秒"

    async def _try_generate_card(
        self,
        streamer_name: str,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo],
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> Optional[bytes]:
        """尝试生成开播卡片图片，失败返回 None（触发降级）"""
        try:
            from .card_generator import generate_live_start_card

            return await generate_live_start_card(
                streamer_name=streamer_name,
                user_info=user_info,
                room_info=room_info,
                prefetched_images=prefetched_images,
            )
        except Exception:
            logger.opt(exception=True).error("生成开播卡片失败，将降级为纯文本通知")
            return None

    async def _try_generate_end_card(
        self,
        streamer_name: str,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo],
        duration_seconds: int = 0,
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> Optional[bytes]:
        """尝试生成下播卡片图片，失败返回 None（触发降级）"""
        try:
            from .card_generator import generate_live_end_card

            return await generate_live_end_card(
                streamer_name=streamer_name,
                user_info=user_info,
                room_info=room_info,
                duration_seconds=duration_seconds,
                prefetched_images=prefetched_images,
            )
        except Exception:
            logger.opt(exception=True).error("生成下播卡片失败，将降级为纯文本通知")
            return None

    async def _generate_card_if_needed(
        self,
        status: str,
        streamer_name: str,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo],
        duration_seconds: int,
        prefetched_images: Optional[PrefetchImages],
    ) -> Optional[bytes]:
        if not self.template_uses_card(status):
            return None

        if status == "start":
            return await self._try_generate_card(
                streamer_name, user_info, room_info, prefetched_images
            )
        return await self._try_generate_end_card(
            streamer_name,
            user_info,
            room_info,
            duration_seconds,
            prefetched_images,
        )

    async def _send_group_message(
        self,
        group_id: str,
        message: Message,
        status: str,
        *,
        pending: PendingDelivery,
        on_part_sent: DeliveryProgressCallback,
    ) -> TargetDelivery:
        try:
            await send_group(
                group_id,
                message,
                at_all=pending.at_all,
                at_all_fallback=LIVE_AT_ALL_FALLBACK,
                start=pending.group_starts.get(group_id, 0),
                on_part_sent=partial(on_part_sent, "group", group_id),
            )
            logger.success("直播{}通知已发送到群组 {}", status, group_id)
            return TargetDelivery("group", group_id, True)
        except LoggedQQApiError as exc:
            return TargetDelivery("group", group_id, False, str(exc))
        except Exception as exc:
            logger.opt(exception=True).error(
                "发送通知到群组 {} 失败: {}", group_id, exc
            )
            return TargetDelivery("group", group_id, False, str(exc))

    async def _send_private_message(
        self,
        user_id: str,
        message: Message,
        status: str,
        *,
        pending: PendingDelivery,
        on_part_sent: DeliveryProgressCallback,
    ) -> TargetDelivery:
        try:
            await send_user(
                user_id,
                message,
                start=pending.user_starts.get(user_id, 0),
                on_part_sent=partial(on_part_sent, "user", user_id),
            )
            logger.success("直播{}通知已发送到好友 {}", status, user_id)
            return TargetDelivery("user", user_id, True)
        except LoggedQQApiError as exc:
            return TargetDelivery("user", user_id, False, str(exc))
        except Exception as exc:
            logger.opt(exception=True).error("发送通知到好友 {} 失败: {}", user_id, exc)
            return TargetDelivery("user", user_id, False, str(exc))

    async def send_notification(
        self,
        status: str,
        streamer_name: str,
        room_info: Optional[RoomInfo],
        target_groups: List[str],
        target_users: Optional[List[str]] = None,
        user_info: Optional[UserInfo] = None,
        duration_seconds: int = 0,
        at_all_enabled: bool = False,
        prefetched_images: Optional[PrefetchImages] = None,
        pending: PendingDelivery | None = None,
        on_prepared: Callable[[PendingDelivery], Awaitable[None]] | None = None,
        on_part_sent: DeliveryProgressCallback | None = None,
    ) -> DeliveryResult:
        """沿目标协议发送开播/下播通知，续传复用已准备的消息。"""
        target_users = target_users or []
        if not target_groups and not target_users:
            return empty_delivery_result()
        if not messaging_bots():
            return DeliveryResult(
                targets=[
                    TargetDelivery(kind, target, False, "没有可用的机器人实例")
                    for kind, ids in (("group", target_groups), ("user", target_users))
                    for target in ids
                ]
            )
        if pending is None:
            card = await self._generate_card_if_needed(
                status,
                streamer_name,
                user_info,
                room_info,
                duration_seconds,
                prefetched_images,
            )
            if status == "start":
                message = self.build_start_message(
                    streamer_name=streamer_name, room_info=room_info, card_image=card
                )
            else:
                message = self.build_end_message(
                    streamer_name=streamer_name,
                    duration_seconds=duration_seconds,
                    card_image=card,
                )
            pending = PendingDelivery(
                message,
                list(target_groups),
                list(target_users),
                at_all=at_all_enabled and status == "start",
            )
        else:
            pending.groups = [gid for gid in pending.groups if gid in target_groups]
            pending.users = [uid for uid in pending.users if uid in target_users]
        if on_prepared is not None:
            await on_prepared(pending)

        async def checkpoint(kind: str, target: str, next_part: int) -> None:
            starts = pending.group_starts if kind == "group" else pending.user_starts
            starts[target] = next_part
            if on_part_sent is not None:
                await on_part_sent(kind, target, next_part)

        targets = []
        for group in pending.groups:
            targets.append(
                await self._send_group_message(
                    group,
                    pending.message,
                    status,
                    pending=pending,
                    on_part_sent=checkpoint,
                )
            )
        for user in pending.users:
            targets.append(
                await self._send_private_message(
                    user,
                    pending.message,
                    status,
                    pending=pending,
                    on_part_sent=checkpoint,
                )
            )
        return DeliveryResult(targets=targets)


notification_sender: Optional[LiveNotificationSender] = None


def get_sender(
    include_room_info: bool = True,
    templates: Optional[LiveMessageTemplates] = None,
) -> LiveNotificationSender:
    """获取或创建发送器实例"""
    global notification_sender
    if notification_sender is None:
        notification_sender = LiveNotificationSender(
            include_room_info=include_room_info,
            templates=templates,
        )
    return notification_sender
