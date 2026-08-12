"""直播监控通知投递编排与 pending 重试逻辑。"""

import asyncio
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
        # ponytail: per-room lock；短播时 end 须等 in-flight start 写完 pending
        self._room_locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, room_id: str) -> asyncio.Lock:
        lock = self._room_locks.get(room_id)
        if lock is None:
            lock = asyncio.Lock()
            self._room_locks[room_id] = lock
        return lock

    def supersede_pending_end(self, room_id: str, state: LiveRoomState) -> None:
        """新一轮开播时放弃已过期的待投递下播通知，避免 pending 标志永久滞留。"""
        if not state.pending_end:
            return
        logger.warning(
            "房间 {} 在新一轮开播前仍有未投递的下播通知，已放弃重试", room_id
        )
        state.clear_pending_end()

    @staticmethod
    def _mark_pending_start_retry(state: LiveRoomState) -> None:
        """投递抛异常时标记待重试；空目标列表表示下次走完整 mapping。"""
        state.pending_start = True
        state.pending_start_groups = []
        state.pending_start_users = []

    @staticmethod
    def _mark_pending_end_retry(state: LiveRoomState) -> None:
        state.pending_end = True
        state.pending_end_groups = []
        state.pending_end_users = []

    async def deliver_pending_start_before_end(
        self,
        room_id: str,
        state: LiveRoomState,
        *,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo] = None,
        prefetched_images: Optional[PrefetchImages] = None,
    ) -> None:
        """关播前补发仍未投递成功的开播通知，避免短播时首播失败后标志被直接清除。"""
        if not state.pending_start:
            return

        effective_room_info = (
            room_info
            if room_info is not None
            else (state.last_live_room_info or state.room_info)
        )
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
            user_info=user_info or state.last_live_user_info or state.user_info,
            prefetched_images=prefetched_images,
        )
        if state.pending_start:
            logger.warning(
                "房间 {} 关播前补发开播通知仍未成功，已放弃待投递标志", room_id
            )
            state.clear_pending_start()

    async def deliver_observed_live_start(
        self,
        room_id: str,
        state: LiveRoomState,
        *,
        room_info: RoomInfo,
        user_info: Optional[UserInfo],
        prefetched,
        observed_status,
        start_time: int,
        confirm_observed_status,
        retry_pending,
        log_label: str = "确认开播",
    ) -> None:
        """确认开播：先同步观测状态，再投递开播通知。

        必须在任何 await 投递之前把 ``previous_status`` 设为 LIVE，否则
        WebSocket 与 API 轮询会在卡片生成窗口内各自再发一次开播通知。
        """
        async with self._lock_for(room_id):
            if state.previous_status == LiveStatus.LIVE:
                return

            streamer_name = (
                (user_info or state.user_info).name
                if (user_info or state.user_info)
                else f"房间{room_id}"
            )
            logger.info("{}: {} (房间 {})", log_label, streamer_name, room_id)
            self.supersede_pending_end(room_id, state)
            await confirm_observed_status(
                room_id,
                state,
                room_info,
                user_info,
                observed_status,
                start_time=start_time,
            )
            try:
                await self.deliver_start(
                    room_id,
                    state,
                    room_info=room_info,
                    user_info=user_info,
                    prefetched_images=prefetched
                    if self._sender.template_uses_card("start")
                    else None,
                )
            except asyncio.CancelledError:
                # DanmakuClient.stop() 会取消 in-flight 回调；先记账再向上抛
                self._mark_pending_start_retry(state)
                raise
            except Exception:
                # confirm 已推进状态；无 pending 则后续轮询看不到变迁、永不重试
                logger.opt(exception=True).error(
                    "房间 {} 开播通知投递异常，已标记待重试", room_id
                )
                self._mark_pending_start_retry(state)
            await retry_pending(
                room_id,
                state,
                room_info,
                user_info,
                prefetched_start=prefetched,
                skip_start=True,
            )

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
        与开播共用 per-room lock，避免短播时 end 抢在 in-flight start 写完
        ``pending_start`` 之前跑完补发检查。
        """
        async with self._lock_for(room_id):
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
                if state.previous_status != observed_status:
                    state.observation_epoch += 1
                state.previous_status = observed_status
                logger.warning(
                    "房间 {} 关播时缺少房间快照，已更新状态并跳过投递", room_id
                )
                return

            # 离线 API 快照常把 live_start_time 清零；补发 start 须用直播中快照
            pending_start_room_info = state.room_info or state.last_live_room_info
            pending_start_user_info = state.user_info or state.last_live_user_info

            await confirm_observed_status(
                room_id,
                state,
                resolved_room_info,
                user_info,
                observed_status,
            )
            try:
                await self.deliver_pending_start_before_end(
                    room_id,
                    state,
                    user_info=user_info or pending_start_user_info,
                    room_info=pending_start_room_info,
                    prefetched_images=prefetched
                    if self._sender.template_uses_card("start")
                    else None,
                )
            except asyncio.CancelledError:
                # confirm 已离线且 end 未跑：同时保留 start/end，供后续有序重试
                if not state.pending_start:
                    self._mark_pending_start_retry(state)
                self._mark_pending_end_retry(state)
                raise
            except Exception:
                logger.opt(exception=True).error(
                    "房间 {} 关播前补发开播通知异常，已放弃待投递标志", room_id
                )
                state.clear_pending_start()
            try:
                await self.deliver_end(
                    room_id,
                    state,
                    room_info=resolved_room_info,
                    user_info=user_info,
                    prefetched_images=prefetched
                    if self._sender.template_uses_card("end")
                    else None,
                )
            except asyncio.CancelledError:
                self._mark_pending_end_retry(state)
                raise
            except Exception:
                logger.opt(exception=True).error(
                    "房间 {} 下播通知投递异常，已标记待重试", room_id
                )
                self._mark_pending_end_retry(state)
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
        if not skip_start and state.pending_start:
            if state.previous_status == LiveStatus.LIVE:
                # 过期轮询可能传入离线快照；pending start 须用开播快照
                start_room = state.last_live_room_info or room_info
                start_user = state.last_live_user_info or user_info
                logger.info("重试房间 {} 待投递的开播通知", room_id)
                await self.deliver_start(
                    room_id,
                    state,
                    room_info=start_room,
                    user_info=start_user,
                    prefetched_images=prefetched_start,
                )
            else:
                # 离线后仍可能有未完成的 start（短播取消等），先于 end 补发
                await self.deliver_pending_start_before_end(
                    room_id,
                    state,
                    user_info=state.last_live_user_info or user_info,
                    room_info=state.last_live_room_info,
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
