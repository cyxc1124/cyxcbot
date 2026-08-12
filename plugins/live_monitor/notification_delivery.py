"""直播监控通知投递编排与 pending 重试逻辑。"""

from typing import Callable, Optional

from nonebot.log import logger

from shared.notify.delivery import DeliveryResult, empty_delivery_result
from utils.bilibili_api import LiveStatus, RoomInfo, UserInfo

from .card_generator import PrefetchImages
from .models import LiveRoomState
from .sender import LiveNotificationSender


def failed_target_ids(delivery: DeliveryResult) -> tuple[list[str], list[str]]:
    groups = [
        target.target_id
        for target in delivery.targets
        if target.target_type == "group" and not target.success
    ]
    users = [
        target.target_id
        for target in delivery.targets
        if target.target_type == "user" and not target.success
    ]
    return groups, users


class LiveNotificationDelivery:
    """封装开播/下播通知投递与 pending 重试编排。"""

    def __init__(
        self,
        sender: LiveNotificationSender,
        *,
        get_group_mapping: Callable[[], dict[str, list[str]]],
        get_user_mapping: Callable[[], dict[str, list[str]]],
        get_at_all: Callable[[], dict[str, bool]],
    ):
        self._sender = sender
        self._get_group_mapping = get_group_mapping
        self._get_user_mapping = get_user_mapping
        self._get_at_all = get_at_all

    def supersede_pending_end(self, room_id: str, state: LiveRoomState) -> None:
        """新一轮开播时放弃已过期的待投递下播通知，避免 pending 标志永久滞留。"""
        if not state.pending_end:
            return
        logger.warning(
            "房间 {} 在新一轮开播前仍有未投递的下播通知，已放弃重试", room_id
        )
        state.clear_pending_end()

    async def deliver_pending_start_before_end(
        self,
        room_id: str,
        state: LiveRoomState,
        *,
        user_info: Optional[UserInfo],
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> None:
        """关播前补发仍未投递成功的开播通知，避免短播时首播失败后标志被直接清除。"""
        if not state.pending_start:
            return

        effective_room_info = state.room_info
        if effective_room_info is None:
            logger.warning(
                "房间 {} 关播时仍有待投递开播通知，但缺少房间快照，已放弃", room_id
            )
            state.clear_pending_start()
            return

        logger.info("房间 {} 关播前补发待投递的开播通知", room_id)
        await self.deliver_start(
            room_id,
            state,
            room_info=effective_room_info,
            user_info=user_info or state.user_info,
            prefetched_images=prefetched_images,
        )
        if state.pending_start:
            logger.warning(
                "房间 {} 关播前补发开播通知仍未成功，已放弃待投递标志", room_id
            )
            state.clear_pending_start()

    async def deliver_observed_live_end(
        self,
        room_id: str,
        state: LiveRoomState,
        *,
        room_info,
        user_info: Optional[UserInfo],
        prefetched,
        observed_status,
        confirm_observed_status,
        retry_pending,
    ) -> None:
        """确认关播：先同步观测状态，再补发 pending start 并投递关播。

        必须在任何 await 投递之前把 ``previous_status`` 移出 LIVE，否则
        WebSocket 与 API 轮询会在卡片生成窗口内各自再发一次下播通知。
        """
        # ponytail: asyncio 单线程下，check→confirm 之间无 await 即可互斥双路径
        if state.previous_status != LiveStatus.LIVE:
            return

        resolved_room_info = room_info or state.room_info
        streamer_name = (
            (user_info or state.user_info).name
            if (user_info or state.user_info)
            else f"房间{room_id}"
        )
        logger.info("确认关播: {} (房间 {})", streamer_name, room_id)
        if resolved_room_info is None:
            state.previous_status = observed_status
            logger.warning("房间 {} 关播时缺少房间快照，已更新状态并跳过投递", room_id)
            return

        await confirm_observed_status(
            room_id,
            state,
            resolved_room_info,
            user_info,
            observed_status,
        )
        await self.deliver_pending_start_before_end(
            room_id,
            state,
            user_info=user_info,
            prefetched_images=prefetched
            if self._sender.template_uses_card("start")
            else None,
        )
        await self.deliver_end(
            room_id,
            state,
            room_info=resolved_room_info,
            user_info=user_info,
            prefetched_images=prefetched
            if self._sender.template_uses_card("end")
            else None,
        )
        await retry_pending(
            room_id,
            state,
            resolved_room_info,
            user_info,
            prefetched_end=prefetched,
            skip_end=True,
        )

    async def deliver_start(
        self,
        room_id: str,
        state: LiveRoomState,
        *,
        room_info: RoomInfo,
        user_info: Optional[UserInfo],
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> bool:
        if state.pending_start and (
            state.pending_start_groups or state.pending_start_users
        ):
            target_groups = state.pending_start_groups
            target_users = state.pending_start_users
        else:
            target_groups = None
            target_users = None

        delivery = await self._send_notification(
            room_id,
            "start",
            state,
            prefetched_images=prefetched_images,
            room_info=room_info,
            user_info=user_info,
            target_groups=target_groups,
            target_users=target_users,
        )
        if delivery.all_succeeded:
            state.clear_pending_start()
            return True

        failed_groups, failed_users = failed_target_ids(delivery)
        state.pending_start = True
        state.pending_start_groups = failed_groups
        state.pending_start_users = failed_users
        return False

    async def deliver_end(
        self,
        room_id: str,
        state: LiveRoomState,
        *,
        room_info: Optional[RoomInfo],
        user_info: Optional[UserInfo],
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> bool:
        if state.pending_end and (state.pending_end_groups or state.pending_end_users):
            target_groups = state.pending_end_groups
            target_users = state.pending_end_users
        else:
            target_groups = None
            target_users = None

        delivery = await self._send_notification(
            room_id,
            "end",
            state,
            prefetched_images=prefetched_images,
            room_info=room_info,
            user_info=user_info,
            target_groups=target_groups,
            target_users=target_users,
        )
        if delivery.all_succeeded:
            state.clear_pending_end()
            return True

        failed_groups, failed_users = failed_target_ids(delivery)
        state.pending_end = True
        state.pending_end_groups = failed_groups
        state.pending_end_users = failed_users
        return False

    async def retry_pending(
        self,
        room_id: str,
        state: LiveRoomState,
        room_info: RoomInfo,
        user_info: Optional[UserInfo],
        *,
        prefetched_start: Optional[PrefetchImages] = None,
        prefetched_end: Optional[PrefetchImages] = None,
        skip_start: bool = False,
        skip_end: bool = False,
    ) -> None:
        if (
            not skip_start
            and state.pending_start
            and state.previous_status == LiveStatus.LIVE
        ):
            logger.info("重试房间 {} 待投递的开播通知", room_id)
            await self.deliver_start(
                room_id,
                state,
                room_info=room_info,
                user_info=user_info,
                prefetched_images=prefetched_start,
            )

        effective_room_info = room_info or state.room_info
        if (
            not skip_end
            and state.pending_end
            and state.previous_status != LiveStatus.LIVE
            and effective_room_info is not None
        ):
            logger.info("重试房间 {} 待投递的下播通知", room_id)
            await self.deliver_end(
                room_id,
                state,
                room_info=effective_room_info,
                user_info=user_info,
                prefetched_images=prefetched_end,
            )

    async def _send_notification(
        self,
        room_id: str,
        status: str,
        state: LiveRoomState,
        prefetched_images: Optional[PrefetchImages] = None,
        *,
        room_info: Optional[RoomInfo] = None,
        user_info: Optional[UserInfo] = None,
        target_groups: Optional[list[str]] = None,
        target_users: Optional[list[str]] = None,
    ) -> DeliveryResult:
        """发送直播通知，全部目标投递成功时返回 all_succeeded。"""
        group_mapping = self._get_group_mapping()
        user_mapping = self._get_user_mapping()
        groups = (
            target_groups
            if target_groups is not None
            else group_mapping.get(room_id, [])
        )
        users = (
            target_users if target_users is not None else user_mapping.get(room_id, [])
        )
        if not groups and not users:
            logger.warning("房间 {} 没有配置推送目标", room_id)
            return empty_delivery_result()

        effective_room_info = room_info if room_info is not None else state.room_info
        effective_user_info = user_info if user_info is not None else state.user_info

        streamer_name = (
            effective_user_info.name if effective_user_info else f"房间{room_id}"
        )

        duration_seconds = state.get_duration_seconds() if status == "end" else 0

        delivery = await self._sender.send_notification(
            status=status,
            streamer_name=streamer_name,
            room_info=effective_room_info,
            target_groups=groups,
            target_users=users,
            user_info=effective_user_info,
            duration_seconds=duration_seconds,
            at_all_enabled=self._get_at_all().get(room_id, True),
            prefetched_images=prefetched_images,
        )
        if delivery.all_succeeded:
            return delivery

        failed_targets = [
            f"{target.target_type}:{target.target_id}"
            for target in delivery.targets
            if not target.success
        ]
        logger.warning(
            "直播{}通知投递未全部成功: room_id={} failed={}",
            status,
            room_id,
            failed_targets,
        )
        return delivery
