"""
B站直播监控核心模块
负责监控直播间状态变化并发送通知
参考 blrec 的 LiveMonitor 设计

监控方式：
1. WebSocket 弹幕监听（主要）：实时监听 LIVE/PREPARING 命令
2. API 轮询（备用）：定时检查直播状态，防止 WebSocket 漏消息
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from nonebot.log import logger

from shared.config.service import get_config_service
from shared.monitor.background_task import spawn_background_task
from shared.monitor.check_cycle import CheckCycleLogger
from shared.monitor.concurrency import run_with_concurrency
from shared.monitor.poll_schedule import (
    LIVE_DANMAKU_CLIENT_START_GAP_SECONDS,
    resolve_live_poll_interval_seconds,
)
from utils.bilibili_api import LiveStatus, RoomInfo, UserInfo, api_manager

from .card_generator import (
    close_card_image_downloader,
    init_card_image_downloader,
    prefetch_card_images,
)
from .config import Config
from .danmaku_client import DanmakuClient
from .models import LiveRoomState
from .notification_delivery import LiveNotificationDelivery
from .poll_scheduler import register_poll_job, remove_poll_job
from .sender import LiveNotificationSender
from .state_store import LiveMonitorStateStore

# 全局监控实例
live_monitor_instance: Optional["LiveMonitor"] = None
_config_reload_registered = False
_lifecycle_lock = asyncio.Lock()


async def sync_from_config_reload(snapshot) -> None:
    """Start, stop, or hot-reload live monitor to match config snapshot."""
    has_targets = bool(snapshot.live_monitor_mapping)

    if live_monitor_instance is None:
        if has_targets:
            await start_live_monitor()
        return

    if not has_targets:
        # 先同步配置并移除房间状态，避免 in-flight 检查仍持有旧 mapping 误推送。
        await live_monitor_instance.reload_config()
        await stop_live_monitor()
        return

    await live_monitor_instance.reload_config()


async def _on_config_reload(snapshot):
    await sync_from_config_reload(snapshot)


def _ensure_config_reload_registered() -> None:
    global _config_reload_registered
    if not _config_reload_registered:
        get_config_service().register_reload_callback(_on_config_reload)
        _config_reload_registered = True


class LiveMonitor:
    """B站直播监控核心类

    双重监控机制：
    1. WebSocket 弹幕客户端：实时监听开播/关播信号（秒级响应）
    2. API 轮询：定时检查状态（备用，防止 WebSocket 漏消息）
    """

    def __init__(self, config: Config):
        self.config = config
        self.is_running = False
        # 房间状态缓存: room_id -> LiveRoomState
        self.room_states: Dict[str, LiveRoomState] = {}
        # 是否已完成首次基准记录（避免启动时已开播的房间误推送）
        self.initialized_rooms: Dict[str, bool] = {}
        # WebSocket 客户端: room_id -> DanmakuClient
        self._danmaku_clients: Dict[str, DanmakuClient] = {}
        # 每次注册客户端时递增，用于忽略过期的 in-flight start 失败
        self._danmaku_client_epoch: Dict[str, int] = {}
        # aiohttp session for WebSocket
        self._ws_session: Optional[aiohttp.ClientSession] = None
        # 通知发送器
        self._sender = LiveNotificationSender(
            include_room_info=config.include_room_info,
            templates=config.message_templates,
        )
        self._state_store = LiveMonitorStateStore()
        self._delivery = LiveNotificationDelivery(
            self._sender,
            get_group_mapping=lambda: self.config.live_monitor_mapping,
            get_user_mapping=lambda: self.config.live_monitor_user_mapping,
            get_at_all=lambda: self.config.live_at_all,
        )
        self._cycle_logger = CheckCycleLogger("直播监控")
        self.last_check_at: Optional[str] = None
        self.checks_total = 0

    def _touch_last_check_at(self) -> None:
        self.last_check_at = datetime.now().isoformat(timespec="seconds")

    def _configured_room_ids(self) -> list[str]:
        return list(self.config.live_monitor_mapping.keys())

    def _is_active_room(self, room_id: str) -> bool:
        return room_id in self.config.live_monitor_mapping

    def _scheduled_poll_interval_seconds(self) -> int:
        return resolve_live_poll_interval_seconds(
            self.config.monitor_interval,
            use_websocket=self.config.use_websocket,
        )

    def _is_current_room_state(self, room_id: str, state: LiveRoomState) -> bool:
        """_is_active_room 校验配置映射；本方法校验 state 是否仍为 room_states 当前条目。"""
        return self.room_states.get(room_id) is state

    async def _delete_persisted_state(self, room_id: str) -> None:
        """清除 DB 中已停用/移除房间的持久化状态。"""
        await self._state_store.delete(room_id)

    async def _remove_room(self, room_id: str) -> None:
        """停止监控并从运行时状态中移除房间。"""
        client = self._danmaku_clients.pop(room_id, None)
        if client:
            try:
                await client.stop()
                logger.debug("房间 {} WebSocket 监控已停止（配置已移除）", room_id)
            except Exception:
                logger.opt(exception=True).warning(
                    "停止房间 {} 弹幕客户端时出错", room_id
                )
        self._danmaku_client_epoch.pop(room_id, None)
        self.room_states.pop(room_id, None)
        self.initialized_rooms.pop(room_id, None)

    async def init_resources(self):
        """初始化资源"""
        # 初始化API管理器
        await api_manager.init(self.config.bilibili_cookie)

        # 初始化 WebSocket session
        self._ws_session = aiohttp.ClientSession()

        await init_card_image_downloader()

        # 初始化房间状态
        for room_id in self.config.live_monitor_mapping.keys():
            if room_id not in self.room_states:
                self.room_states[room_id] = LiveRoomState(room_id=int(room_id))
            if room_id not in self.initialized_rooms:
                self.initialized_rooms[room_id] = False

        await self._load_persisted_states()

        if not self.config.bilibili_cookie:
            logger.warning("直播监控: 未登录 B 站 直播间信息可能无法获取")

        logger.info("直播监控已初始化，监控房间数: {}", len(self.room_states))

    async def _load_persisted_states(self):
        room_ids = list(self.config.live_monitor_mapping.keys())
        await self._state_store.load(self.room_states, room_ids)

    async def _persist_state(self, room_id: str):
        if not self._is_active_room(room_id):
            return
        state = self.room_states.get(room_id)
        if not state:
            return
        await self._state_store.persist(room_id, state)

    async def reload_config(self):
        old_interval = self.config.monitor_interval
        old_ws = self.config.use_websocket
        old_configured_room_ids = set(self.config.live_monitor_mapping.keys())
        old_room_ids = set(self.room_states.keys())
        old_cookie = self.config.bilibili_cookie
        self.config = Config.from_service()

        await api_manager.init(self.config.bilibili_cookie)

        new_room_ids_set = set(self.config.live_monitor_mapping.keys())
        removed_room_ids = old_room_ids - new_room_ids_set
        for room_id in removed_room_ids:
            try:
                await self._remove_room(room_id)
                await self._delete_persisted_state(room_id)
            except Exception:
                logger.opt(exception=True).error("移除房间 {} 监控失败", room_id)
        if removed_room_ids:
            logger.info(
                "直播监控已移除 {} 个不再配置的房间: {}",
                len(removed_room_ids),
                ", ".join(sorted(removed_room_ids)),
            )

        readded_room_ids = new_room_ids_set - old_configured_room_ids
        for room_id in readded_room_ids:
            try:
                self.room_states.pop(room_id, None)
                self.initialized_rooms.pop(room_id, None)
                stale_client = self._danmaku_clients.pop(room_id, None)
                if stale_client:
                    try:
                        await stale_client.stop()
                    except Exception:
                        logger.opt(exception=True).warning(
                            "停止房间 {} 弹幕客户端时出错", room_id
                        )
                await self._delete_persisted_state(room_id)
            except Exception:
                logger.opt(exception=True).error("重置房间 {} 持久化状态失败", room_id)
        if readded_room_ids:
            logger.info(
                "直播监控已重新启用 {} 个房间，已重置监控状态: {}",
                len(readded_room_ids),
                ", ".join(sorted(readded_room_ids)),
            )

        new_room_ids: list[str] = list(readded_room_ids)
        for room_id in self.config.live_monitor_mapping.keys():
            if room_id not in self.room_states:
                self.room_states[room_id] = LiveRoomState(room_id=int(room_id))
                self.initialized_rooms[room_id] = False
                if room_id not in new_room_ids:
                    new_room_ids.append(room_id)
            elif room_id not in self.initialized_rooms:
                self.initialized_rooms[room_id] = False

        if self.is_running:
            for room_id in new_room_ids:
                await self._initialize_room(room_id)

            poll_interval = self._scheduled_poll_interval_seconds()
            if (
                old_interval != self.config.monitor_interval
                or old_ws != self.config.use_websocket
            ):
                register_poll_job(self._check_all_rooms, poll_interval)
                logger.info("直播监控轮询间隔已更新为 {}秒", poll_interval)

            if old_ws != self.config.use_websocket:
                if self.config.use_websocket:
                    await self._start_danmaku_clients()
                else:
                    await self._stop_danmaku_clients()
            elif self.config.use_websocket:
                if old_cookie != self.config.bilibili_cookie:
                    existing_room_ids = [
                        room_id
                        for room_id in self._configured_room_ids()
                        if room_id not in new_room_ids
                    ]
                    for room_id in existing_room_ids:
                        try:
                            await self._restart_single_danmaku_client(room_id)
                        except Exception:
                            logger.opt(exception=True).error(
                                "房间 {} Cookie 热更新 WebSocket 客户端失败", room_id
                            )
                        # 避免同时连接过多
                        await asyncio.sleep(LIVE_DANMAKU_CLIENT_START_GAP_SECONDS)
                    if existing_room_ids:
                        logger.info(
                            "直播监控 Cookie 已变更，已更新 {} 个 WebSocket 客户端",
                            len(existing_room_ids),
                        )

                for room_id in new_room_ids:
                    try:
                        await self._start_single_danmaku_client(room_id)
                    except Exception:
                        logger.opt(exception=True).error(
                            "房间 {} 弹幕客户端启动失败", room_id
                        )

        self._sender.include_room_info = self.config.include_room_info
        self._sender.templates = self.config.message_templates

        poll_interval = self._scheduled_poll_interval_seconds()
        logger.info(
            "直播监控配置已热重载: {} 个房间, 轮询间隔 {}秒, WebSocket={}",
            len(self.config.live_monitor_mapping),
            poll_interval,
            "开启" if self.config.use_websocket else "关闭",
        )

    async def start_monitoring(self):
        """启动监控"""
        self.is_running = True

        # 初始化资源
        await self.init_resources()

        # 每次启动都重新建立基准，避免启动时已开播的房间误推送
        for room_id in self.room_states:
            self.initialized_rooms[room_id] = False

        # 首次检查，初始化各房间状态
        logger.info("正在初始化各直播间状态...")
        await self._init_room_states()

        # 根据配置决定监控方式
        if self.config.use_websocket:
            # 启动 WebSocket 弹幕客户端（主要监控方式）
            logger.info("正在启动 WebSocket 实时监控...")
            await self._start_danmaku_clients()

            # API 轮询作为备用，间隔较长
            poll_interval = self._scheduled_poll_interval_seconds()
            logger.info(
                "直播监控已启动：WebSocket 实时监控 + API 轮询备用（间隔 {}秒）",
                poll_interval,
            )
        else:
            # 仅使用 API 轮询
            poll_interval = self._scheduled_poll_interval_seconds()
            logger.info("直播监控已启动：仅 API 轮询模式（间隔 {}秒）", poll_interval)

        register_poll_job(self._check_all_rooms, poll_interval)

    async def stop_monitoring(self):
        """停止监控"""
        logger.info("正在停止直播监控...")
        self.is_running = False

        # 停止所有 WebSocket 客户端
        await self._stop_danmaku_clients()

        # 关闭 WebSocket session
        if self._ws_session and not self._ws_session.closed:
            await self._ws_session.close()
            self._ws_session = None

        remove_poll_job()

        # 关闭API管理器
        await api_manager.close()

        await close_card_image_downloader()

        logger.info("直播监控已完全停止")

    async def _start_danmaku_clients(self):
        """启动所有房间的弹幕客户端"""
        for room_id in self._configured_room_ids():
            try:
                await self._start_single_danmaku_client(room_id)
            except Exception:
                logger.opt(exception=True).error("房间 {} 弹幕客户端启动失败", room_id)
            # 避免同时连接过多
            await asyncio.sleep(LIVE_DANMAKU_CLIENT_START_GAP_SECONDS)

    async def _restart_single_danmaku_client(self, room_id: str) -> None:
        """停止并重建单个房间的弹幕客户端（凭据变更等场景）。"""
        old_client = self._danmaku_clients.pop(room_id, None)
        try:
            await self._start_single_danmaku_client(room_id)
        except Exception:
            if old_client is not None:
                self._danmaku_clients[room_id] = old_client
            raise

        if old_client:
            try:
                await old_client.stop()
                logger.debug("房间 {} WebSocket 监控已停止（凭据变更）", room_id)
            except Exception:
                logger.opt(exception=True).warning(
                    "停止房间 {} 弹幕客户端时出错", room_id
                )

    async def _start_single_danmaku_client(self, room_id: str):
        """启动单个房间的弹幕客户端"""
        if room_id in self._danmaku_clients:
            return

        # 创建弹幕客户端
        client = DanmakuClient(
            session=self._ws_session,
            room_id=int(room_id),
            cookie=self.config.bilibili_cookie,
        )

        async def on_live():
            if self._danmaku_clients.get(room_id) is client:
                await self._handle_live_signal(room_id)

        async def on_preparing(round_status: Optional[int]):
            if self._danmaku_clients.get(room_id) is client:
                await self._handle_preparing_signal(room_id, round_status)

        async def on_room_change(data: dict):
            if self._danmaku_clients.get(room_id) is client:
                await self._handle_room_change(room_id, data)

        client.on_live = on_live
        client.on_preparing = on_preparing
        client.on_room_change = on_room_change

        start_epoch = self._danmaku_client_epoch.get(room_id, 0) + 1
        self._danmaku_client_epoch[room_id] = start_epoch
        self._danmaku_clients[room_id] = client
        try:
            await client.start()
        except Exception:
            # 仅移除本次 epoch 仍有效的注册，避免 Cookie 热重载等场景下
            # 过期的 in-flight 启动失败误删已替换或已恢复的旧客户端。
            if (
                self._danmaku_client_epoch.get(room_id) == start_epoch
                and self._danmaku_clients.get(room_id) is client
            ):
                self._danmaku_clients.pop(room_id, None)
            raise
        logger.debug("房间 {} WebSocket 监控已启动", room_id)

    async def _stop_danmaku_clients(self):
        """停止所有弹幕客户端"""
        for room_id, client in self._danmaku_clients.items():
            try:
                await client.stop()
                logger.debug("房间 {} 弹幕客户端已停止", room_id)
            except Exception:
                logger.opt(exception=True).warning(
                    "停止房间 {} 弹幕客户端时出错", room_id
                )
        self._danmaku_clients.clear()
        self._danmaku_client_epoch.clear()
        logger.info("所有 WebSocket 客户端已停止")

    async def _fetch_room_info_with_prefetch(
        self, room_id: str, status: str, state: LiveRoomState
    ):
        """并行拉取最新房间信息，并在需要卡片时预下载素材。"""
        prefetch_task = None
        if self._sender.template_uses_card(status):
            prefetch_task = asyncio.create_task(
                prefetch_card_images(state.user_info, state.room_info)
            )

        room_info, user_info = await api_manager.get_room_and_user_info(int(room_id))

        prefetched = None
        if prefetch_task:
            try:
                prefetched = await prefetch_task
            except Exception:
                logger.opt(exception=True).warning(
                    "房间 {} 卡片素材预下载失败", room_id
                )

        return room_info, user_info, prefetched

    async def _handle_live_signal(self, room_id: str):
        """处理开播信号（来自 WebSocket）"""
        logger.debug("房间 {} 收到开播信号", room_id)

        if not self._is_active_room(room_id):
            return

        if not self.initialized_rooms.get(room_id, False):
            await self._initialize_room(room_id)
            return

        state = self.room_states.get(room_id)
        if not state:
            return

        # 获取最新房间信息（卡片素材与 API 并行预取）
        room_info, user_info, prefetched = await self._fetch_room_info_with_prefetch(
            room_id, "start", state
        )

        if not room_info:
            logger.debug("房间 {} 获取信息失败", room_id)
            return

        if not self._is_active_room(room_id):
            return
        if not self._is_current_room_state(room_id, state):
            return

        # 检查状态变化
        is_live_began, is_live_ended, new_status, start_time = (
            state.detect_status_change(room_info)
        )

        if is_live_began:
            await self._delivery.deliver_observed_live_start(
                room_id,
                state,
                room_info=room_info,
                user_info=user_info,
                prefetched=prefetched,
                observed_status=new_status,
                start_time=start_time,
                confirm_observed_status=self._confirm_observed_status,
                retry_pending=self._delivery.retry_pending,
                log_label="确认开播",
            )
        elif is_live_ended:
            await self._delivery.deliver_observed_live_end(
                room_id,
                state,
                room_info=room_info,
                user_info=user_info,
                prefetched=prefetched,
                observed_status=new_status,
                confirm_observed_status=self._confirm_observed_status,
                retry_pending=self._delivery.retry_pending,
            )
        else:
            state.sync_observed_status(
                room_info,
                room_info.live_status,
                new_user_info=user_info,
            )

    async def _handle_preparing_signal(self, room_id: str, round_status: Optional[int]):
        """处理关播信号（来自 WebSocket）"""
        logger.debug("房间 {} 收到关播信号 (round={})", room_id, round_status)

        if not self._is_active_room(room_id):
            return

        if not self.initialized_rooms.get(room_id, False):
            await self._initialize_room(room_id)
            return

        state = self.room_states.get(room_id)
        if not state:
            return

        # 获取最新房间信息（卡片素材与 API 并行预取）
        room_info, user_info, prefetched = await self._fetch_room_info_with_prefetch(
            room_id, "end", state
        )

        if not self._is_active_room(room_id):
            return
        if not self._is_current_room_state(room_id, state):
            return

        if room_info:
            _, is_live_ended, observed_status, _ = state.detect_status_change(room_info)
        else:
            is_live_ended = state.previous_status == LiveStatus.LIVE
            observed_status = (
                LiveStatus.ROUND if round_status == 1 else LiveStatus.PREPARING
            )

        if is_live_ended:
            await self._delivery.deliver_observed_live_end(
                room_id,
                state,
                room_info=room_info,
                user_info=user_info,
                prefetched=prefetched,
                observed_status=observed_status,
                confirm_observed_status=self._confirm_observed_status,
                retry_pending=self._delivery.retry_pending,
            )

    async def _handle_room_change(self, room_id: str, data: dict):
        """处理房间信息变更"""
        if not self._is_active_room(room_id):
            return

        state = self.room_states.get(room_id)
        if not state or not state.room_info:
            return

        # 更新标题等信息
        if "title" in data:
            logger.debug("房间 {} 标题变更: {}", room_id, data["title"])

    async def _initialize_room(self, room_id: str) -> bool:
        """记录房间当前直播状态作为基准，不触发推送"""
        if not self._is_active_room(room_id):
            return False

        state = self.room_states.get(room_id)
        if not state:
            return False

        try:
            room_info, user_info = await api_manager.get_room_and_user_info(
                int(room_id)
            )

            if room_info:
                if not self._is_active_room(room_id):
                    return False
                if not self._is_current_room_state(room_id, state):
                    return False

                state.room_info = room_info
                state.user_info = user_info
                state.previous_status = room_info.live_status
                state.clear_pending_start()
                state.clear_pending_end()

                if room_info.is_living():
                    state.start_time = room_info.live_start_time or int(
                        datetime.now().timestamp()
                    )
                    streamer_name = user_info.name if user_info else f"房间{room_id}"
                    logger.info(
                        "房间 {} ({}) 首次基准：当前正在直播，不推送",
                        room_id,
                        streamer_name,
                    )
                else:
                    streamer_name = user_info.name if user_info else f"房间{room_id}"
                    logger.info(
                        "房间 {} ({}) 首次基准：当前未开播", room_id, streamer_name
                    )

                self.initialized_rooms[room_id] = True
                await self._persist_state(room_id)
                return True

            logger.warning("无法获取房间 {} 的初始状态", room_id)
        except Exception:
            logger.opt(exception=True).error("初始化房间 {} 状态失败", room_id)

        return False

    async def _init_room_states(self):
        """初始化所有房间的状态（首次启动时）"""
        for room_id in self.room_states.keys():
            await self._initialize_room(room_id)
            await asyncio.sleep(0.5)

    async def _check_all_rooms(self):
        """检查所有房间的直播状态"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return

        room_ids = self._configured_room_ids()
        results = await run_with_concurrency(room_ids, self._check_room_status)
        for room_id, ok in zip(room_ids, results):
            if isinstance(ok, BaseException):
                self._cycle_logger.record_error(room_id, ok)
            elif ok is False:
                self._cycle_logger.record_failure(room_id)
            else:
                self._cycle_logger.record_success()

        self._cycle_logger.emit_summary()
        self._touch_last_check_at()

    async def _check_room_status(self, room_id: str) -> bool:
        """检查单个房间的直播状态，拉取失败返回 False。"""
        if not self._is_active_room(room_id):
            return True

        self.checks_total += 1

        if not self.initialized_rooms.get(room_id, False):
            await self._initialize_room(room_id)
            return True

        state = self.room_states.get(room_id)
        if not state:
            return True

        need_start_card = self._sender.template_uses_card("start")
        need_end_card = self._sender.template_uses_card("end")
        prefetch_task = None
        if need_start_card or need_end_card:
            prefetch_task = asyncio.create_task(
                prefetch_card_images(state.user_info, state.room_info)
            )

        room_info, user_info = await api_manager.get_room_and_user_info(int(room_id))

        prefetched = None
        if prefetch_task:
            try:
                prefetched = await prefetch_task
            except Exception:
                logger.opt(exception=True).warning(
                    "房间 {} 卡片素材预下载失败", room_id
                )

        if not room_info:
            logger.debug("无法获取房间 {} 的最新状态", room_id)
            return False

        if not self._is_active_room(room_id):
            return True
        if not self._is_current_room_state(room_id, state):
            return True

        # 检测状态变化；观测状态与待投递通知分开跟踪
        is_live_began, is_live_ended, new_status, start_time = (
            state.detect_status_change(room_info)
        )

        # 处理开播事件
        if is_live_began:
            await self._delivery.deliver_observed_live_start(
                room_id,
                state,
                room_info=room_info,
                user_info=user_info,
                prefetched=prefetched,
                observed_status=new_status,
                start_time=start_time,
                confirm_observed_status=self._confirm_observed_status,
                retry_pending=self._delivery.retry_pending,
                log_label="检测到开播",
            )

        # 处理关播事件
        elif is_live_ended:
            streamer_name = user_info.name if user_info else f"房间{room_id}"
            logger.info("检测到关播: {} (房间 {})", streamer_name, room_id)
            await self._delivery.deliver_observed_live_end(
                room_id,
                state,
                room_info=room_info,
                user_info=user_info,
                prefetched=prefetched,
                observed_status=new_status,
                confirm_observed_status=self._confirm_observed_status,
                retry_pending=self._delivery.retry_pending,
            )
        else:
            await self._confirm_observed_status(
                room_id,
                state,
                room_info,
                user_info,
                new_status,
            )
            await self._delivery.retry_pending(
                room_id,
                state,
                room_info,
                user_info,
                prefetched_start=prefetched if need_start_card else None,
                prefetched_end=prefetched if need_end_card else None,
            )

        return True

    async def _confirm_observed_status(
        self,
        room_id: str,
        state: LiveRoomState,
        room_info: RoomInfo,
        user_info: Optional[UserInfo],
        new_status: LiveStatus,
        *,
        start_time: Optional[int] = None,
    ) -> None:
        """同步观测状态并持久化。"""
        state.sync_observed_status(
            room_info,
            new_status,
            new_user_info=user_info,
            start_time=start_time,
        )
        spawn_background_task(
            "直播状态持久化 {}",
            self._persist_state(room_id),
            name_args=(room_id,),
        )

    async def run_manual_check(
        self, room_ids: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """检查指定或全部直播间的状态（手动触发时使用）。"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return {"checked": [], "failed": []}

        rid_list = room_ids if room_ids is not None else self._configured_room_ids()
        cycle = CheckCycleLogger("直播监控（手动）")
        checked: List[str] = []
        failed: List[str] = []

        try:
            results = await run_with_concurrency(rid_list, self._check_room_status)
            for room_id, ok in zip(rid_list, results):
                if isinstance(ok, BaseException):
                    cycle.record_error(room_id, ok)
                    failed.append(room_id)
                elif ok is False:
                    cycle.record_failure(room_id)
                    failed.append(room_id)
                else:
                    cycle.record_success()
                    checked.append(room_id)

            cycle.emit_summary(log_success_at_info=True)
            self._touch_last_check_at()
        except Exception:
            logger.opt(exception=True).error("直播监控检查出错")

        return {"checked": checked, "failed": failed}

    async def check_room_now(self, room_id: str) -> Optional[Dict]:
        """立即检查指定房间的状态（用于手动触发）"""
        room_info, user_info = await api_manager.get_room_and_user_info(int(room_id))

        if room_info:
            return {
                "room_id": room_info.room_id,
                "streamer_name": user_info.name if user_info else f"房间{room_id}",
                "title": room_info.title,
                "is_living": room_info.is_living(),
                "live_status": room_info.live_status.name,
                "area": f"{room_info.parent_area_name} - {room_info.area_name}",
                "online": room_info.online,
            }
        return None


# 插件启动和关闭函数
async def start_live_monitor():
    """启动直播监控"""
    global live_monitor_instance

    async with _lifecycle_lock:
        _ensure_config_reload_registered()

        if live_monitor_instance is not None:
            if live_monitor_instance.is_running:
                logger.warning("直播监控已在运行中")
                return
            live_monitor_instance = None

        config = Config.from_service()

        # 检查是否有配置的房间
        if not config.live_monitor_mapping:
            logger.warning("未配置任何直播间监控，跳过启动")
            return

        group_count = sum(
            len(groups) for groups in config.live_monitor_mapping.values()
        )
        user_count = sum(
            len(users) for users in config.live_monitor_user_mapping.values()
        )
        mode = "WebSocket+轮询备用" if config.use_websocket else "仅轮询"
        logger.info(
            "准备启动直播监控: {} 个房间, {} 个群推送目标, {} 个好友推送目标, "
            "模式 {}, 间隔 {}秒",
            len(config.live_monitor_mapping),
            group_count,
            user_count,
            mode,
            config.monitor_interval,
        )

        try:
            # 创建监控实例
            live_monitor_instance = LiveMonitor(config)

            # 启动监控
            await live_monitor_instance.start_monitoring()

            logger.info("B站直播监控已启动")

        except Exception:
            logger.opt(exception=True).error("启动直播监控失败")
            live_monitor_instance = None


async def stop_live_monitor():
    """停止直播监控"""
    global live_monitor_instance

    async with _lifecycle_lock:
        if not live_monitor_instance:
            return

        logger.info("正在停止直播监控...")

        try:
            await live_monitor_instance.stop_monitoring()
            live_monitor_instance = None
            logger.info("直播监控已完全停止")

        except Exception:
            logger.opt(exception=True).error("停止直播监控时出错")
            live_monitor_instance = None
