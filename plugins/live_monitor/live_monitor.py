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
from typing import Dict, Optional

import aiohttp
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_session

from shared.config.service import get_config_service
from shared.db.models import LiveMonitorState
from shared.monitor.check_cycle import CheckCycleLogger
from utils.bilibili_api import LiveStatus, api_manager

from .card_generator import PrefetchImages, prefetch_card_images
from .config import Config
from .danmaku_client import DanmakuClient
from .models import LiveRoomState
from .sender import LiveNotificationSender

# 全局监控实例
live_monitor_instance: Optional["LiveMonitor"] = None
_config_reload_registered = False


async def _on_config_reload(_snapshot):
    if live_monitor_instance:
        await live_monitor_instance.reload_config()


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
        self._cycle_logger = CheckCycleLogger("直播监控")
        self.last_check_at: Optional[str] = None

    def _touch_last_check_at(self) -> None:
        self.last_check_at = datetime.now().isoformat(timespec="seconds")

    def _configured_room_ids(self) -> list[str]:
        return list(self.config.live_monitor_mapping.keys())

    def _is_active_room(self, room_id: str) -> bool:
        return room_id in self.config.live_monitor_mapping

    def _is_current_room_state(self, room_id: str, state: LiveRoomState) -> bool:
        """_is_active_room 校验配置映射；本方法校验 state 是否仍为 room_states 当前条目。"""
        return self.room_states.get(room_id) is state

    async def _delete_persisted_state(self, room_id: str) -> None:
        """清除 DB 中已停用/移除房间的持久化状态。"""
        session = get_session()
        async with session.begin():
            row = await session.get(LiveMonitorState, room_id)
            if row:
                await session.delete(row)

    async def _remove_room(self, room_id: str) -> None:
        """停止监控并从运行时状态中移除房间。"""
        client = self._danmaku_clients.pop(room_id, None)
        if client:
            try:
                await client.stop()
                logger.debug(f"房间 {room_id} WebSocket 监控已停止（配置已移除）")
            except Exception as e:
                logger.warning(f"停止房间 {room_id} 弹幕客户端时出错: {e}")
        self._danmaku_client_epoch.pop(room_id, None)
        self.room_states.pop(room_id, None)
        self.initialized_rooms.pop(room_id, None)

    async def init_resources(self):
        """初始化资源"""
        # 初始化API管理器
        await api_manager.init(self.config.bilibili_cookie)

        # 初始化 WebSocket session
        self._ws_session = aiohttp.ClientSession()

        # 初始化房间状态
        for room_id in self.config.live_monitor_mapping.keys():
            if room_id not in self.room_states:
                self.room_states[room_id] = LiveRoomState(room_id=int(room_id))
            if room_id not in self.initialized_rooms:
                self.initialized_rooms[room_id] = False

        await self._load_persisted_states()

        if not self.config.bilibili_cookie:
            logger.warning("直播监控: 未登录 B 站 直播间信息可能无法获取")

        logger.info(f"直播监控已初始化，监控房间数: {len(self.room_states)}")

    async def _load_persisted_states(self):
        session = get_session()
        async with session.begin():
            for room_id in self.config.live_monitor_mapping.keys():
                row = await session.get(LiveMonitorState, room_id)
                if row and room_id in self.room_states:
                    state = self.room_states[room_id]
                    if row.previous_status:
                        from utils.bilibili_api import LiveStatus

                        try:
                            state.previous_status = LiveStatus[row.previous_status]
                        except KeyError:
                            pass
                    if row.start_time:
                        state.start_time = row.start_time

    async def _persist_state(self, room_id: str):
        if not self._is_active_room(room_id):
            return
        state = self.room_states.get(room_id)
        if not state:
            return
        session = get_session()
        async with session.begin():
            row = await session.get(LiveMonitorState, room_id)
            if not row:
                row = LiveMonitorState(room_id=room_id)
                session.add(row)
            row.previous_status = (
                state.previous_status.name if state.previous_status else None
            )
            row.start_time = state.start_time or None
            row.streamer_name = state.user_info.name if state.user_info else None

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
            except Exception as e:
                logger.error(f"移除房间 {room_id} 监控失败: {e}")
        if removed_room_ids:
            logger.info(
                f"直播监控已移除 {len(removed_room_ids)} 个不再配置的房间: "
                f"{', '.join(sorted(removed_room_ids))}"
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
                    except Exception as e:
                        logger.warning(f"停止房间 {room_id} 弹幕客户端时出错: {e}")
                await self._delete_persisted_state(room_id)
            except Exception as e:
                logger.error(f"重置房间 {room_id} 持久化状态失败: {e}")
        if readded_room_ids:
            logger.info(
                f"直播监控已重新启用 {len(readded_room_ids)} 个房间，已重置监控状态: "
                f"{', '.join(sorted(readded_room_ids))}"
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

            poll_interval = (
                max(300, self.config.monitor_interval * 5)
                if self.config.use_websocket
                else self.config.monitor_interval
            )
            if (
                old_interval != self.config.monitor_interval
                or old_ws != self.config.use_websocket
            ):
                scheduler.add_job(
                    self._check_all_rooms,
                    "interval",
                    seconds=poll_interval,
                    id="live_monitor_check",
                    replace_existing=True,
                    max_instances=1,
                    misfire_grace_time=60,
                )
                logger.info(f"直播监控轮询间隔已更新为 {poll_interval}秒")

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
                        except Exception as e:
                            logger.error(
                                f"房间 {room_id} Cookie 热更新 WebSocket 客户端失败: {e}"
                            )
                        # 避免同时连接过多
                        await asyncio.sleep(1)
                    if existing_room_ids:
                        logger.info(
                            f"直播监控 Cookie 已变更，已更新 "
                            f"{len(existing_room_ids)} 个 WebSocket 客户端"
                        )

                for room_id in new_room_ids:
                    try:
                        await self._start_single_danmaku_client(room_id)
                    except Exception as e:
                        logger.error(f"房间 {room_id} 弹幕客户端启动失败: {e}")

        self._sender.include_room_info = self.config.include_room_info
        self._sender.templates = self.config.message_templates

        poll_interval = (
            max(300, self.config.monitor_interval * 5)
            if self.config.use_websocket
            else self.config.monitor_interval
        )
        logger.info(
            f"直播监控配置已热重载: {len(self.config.live_monitor_mapping)} 个房间, "
            f"轮询间隔 {poll_interval}秒, "
            f"WebSocket={'开启' if self.config.use_websocket else '关闭'}"
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
            poll_interval = max(300, self.config.monitor_interval * 5)
            logger.info(
                f"直播监控已启动：WebSocket 实时监控 + API 轮询备用（间隔 {poll_interval}秒）"
            )
        else:
            # 仅使用 API 轮询
            poll_interval = self.config.monitor_interval
            logger.info(f"直播监控已启动：仅 API 轮询模式（间隔 {poll_interval}秒）")

        # 使用APScheduler添加定时任务
        scheduler.add_job(
            self._check_all_rooms,
            "interval",
            seconds=poll_interval,
            id="live_monitor_check",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
        )

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

        # 移除定时任务
        try:
            scheduler.remove_job("live_monitor_check")
            logger.info("直播监控定时任务已移除")
        except Exception as e:
            logger.warning(f"移除定时任务时出错: {e}")

        # 关闭API管理器
        await api_manager.close()

        logger.info("直播监控已完全停止")

    async def _start_danmaku_clients(self):
        """启动所有房间的弹幕客户端"""
        for room_id in self._configured_room_ids():
            try:
                await self._start_single_danmaku_client(room_id)
            except Exception as e:
                logger.error(f"房间 {room_id} 弹幕客户端启动失败: {e}")
            # 避免同时连接过多
            await asyncio.sleep(1)

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
                logger.debug(f"房间 {room_id} WebSocket 监控已停止（凭据变更）")
            except Exception as e:
                logger.warning(f"停止房间 {room_id} 弹幕客户端时出错: {e}")

    async def _start_single_danmaku_client(self, room_id: str):
        """启动单个房间的弹幕客户端"""
        if room_id in self._danmaku_clients:
            return

        # 创建回调函数
        async def on_live():
            await self._handle_live_signal(room_id)

        async def on_preparing(round_status: Optional[int]):
            await self._handle_preparing_signal(room_id, round_status)

        async def on_room_change(data: dict):
            await self._handle_room_change(room_id, data)

        # 创建弹幕客户端
        client = DanmakuClient(
            session=self._ws_session,
            room_id=int(room_id),
            cookie=self.config.bilibili_cookie,
            on_live=on_live,
            on_preparing=on_preparing,
            on_room_change=on_room_change,
        )

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
        logger.debug(f"房间 {room_id} WebSocket 监控已启动")

    async def _stop_danmaku_clients(self):
        """停止所有弹幕客户端"""
        for room_id, client in self._danmaku_clients.items():
            try:
                await client.stop()
                logger.debug(f"房间 {room_id} 弹幕客户端已停止")
            except Exception as e:
                logger.warning(f"停止房间 {room_id} 弹幕客户端时出错: {e}")
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
            except Exception as e:
                logger.warning(f"房间 {room_id} 卡片素材预下载失败: {e}")

        return room_info, user_info, prefetched

    async def _handle_live_signal(self, room_id: str):
        """处理开播信号（来自 WebSocket）"""
        logger.debug(f"房间 {room_id} 收到开播信号")

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
            logger.debug(f"房间 {room_id} 获取信息失败")
            return

        if not self._is_active_room(room_id):
            return
        if not self._is_current_room_state(room_id, state):
            return

        # 检查状态变化
        old_status = state.previous_status

        if old_status != LiveStatus.LIVE and room_info.live_status == LiveStatus.LIVE:
            # 确认是开播
            state.previous_status = LiveStatus.LIVE
            state.room_info = room_info
            state.user_info = user_info
            state.start_time = room_info.live_start_time or int(
                datetime.now().timestamp()
            )

            streamer_name = user_info.name if user_info else f"房间{room_id}"
            logger.info(f"确认开播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(
                room_id, "start", state, prefetched_images=prefetched
            )
        else:
            # 更新状态但不发送通知（可能是重复信号或已经在直播中）
            state.room_info = room_info
            if user_info:
                state.user_info = user_info

    async def _handle_preparing_signal(self, room_id: str, round_status: Optional[int]):
        """处理关播信号（来自 WebSocket）"""
        logger.debug(f"房间 {room_id} 收到关播信号 (round={round_status})")

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

        old_status = state.previous_status

        # 只有之前是直播状态才发送关播通知
        if old_status == LiveStatus.LIVE:
            # 判断是关播还是轮播
            new_status = LiveStatus.ROUND if round_status == 1 else LiveStatus.PREPARING

            state.previous_status = new_status
            if room_info:
                state.room_info = room_info
            if user_info:
                state.user_info = user_info

            streamer_name = (
                state.user_info.name if state.user_info else f"房间{room_id}"
            )
            logger.info(f"确认关播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(
                room_id, "end", state, prefetched_images=prefetched
            )

    async def _handle_room_change(self, room_id: str, data: dict):
        """处理房间信息变更"""
        state = self.room_states.get(room_id)
        if not state or not state.room_info:
            return

        # 更新标题等信息
        if "title" in data:
            logger.debug(f"房间 {room_id} 标题变更: {data['title']}")

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

                if room_info.is_living():
                    state.start_time = room_info.live_start_time or int(
                        datetime.now().timestamp()
                    )
                    streamer_name = user_info.name if user_info else f"房间{room_id}"
                    logger.info(
                        f"房间 {room_id} ({streamer_name}) 首次基准：当前正在直播，不推送"
                    )
                else:
                    streamer_name = user_info.name if user_info else f"房间{room_id}"
                    logger.info(
                        f"房间 {room_id} ({streamer_name}) 首次基准：当前未开播"
                    )

                self.initialized_rooms[room_id] = True
                await self._persist_state(room_id)
                return True

            logger.warning(f"无法获取房间 {room_id} 的初始状态")
        except Exception as e:
            logger.error(f"初始化房间 {room_id} 状态失败: {e}")

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

        for room_id in self._configured_room_ids():
            try:
                ok = await self._check_room_status(room_id)
                if ok is False:
                    self._cycle_logger.record_failure(room_id)
                else:
                    self._cycle_logger.record_success()
            except Exception as e:
                self._cycle_logger.record_error(room_id, e)

            # 避免请求过快
            await asyncio.sleep(0.3)

        self._cycle_logger.emit_summary()
        self._touch_last_check_at()

    async def _check_room_status(self, room_id: str) -> bool:
        """检查单个房间的直播状态，拉取失败返回 False。"""
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
            except Exception as e:
                logger.warning(f"房间 {room_id} 卡片素材预下载失败: {e}")

        if not room_info:
            logger.debug(f"无法获取房间 {room_id} 的最新状态")
            return False

        if not self._is_active_room(room_id):
            return True
        if not self._is_current_room_state(room_id, state):
            return True

        # 更新状态并检测变化
        is_live_began, is_live_ended = state.update_status(room_info, user_info)

        # 处理开播事件
        if is_live_began:
            streamer_name = (
                state.user_info.name if state.user_info else f"房间{room_id}"
            )
            logger.info(f"检测到开播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(
                room_id,
                "start",
                state,
                prefetched_images=prefetched if need_start_card else None,
            )

        # 处理关播事件
        if is_live_ended:
            streamer_name = (
                state.user_info.name if state.user_info else f"房间{room_id}"
            )
            logger.info(f"检测到关播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(
                room_id,
                "end",
                state,
                prefetched_images=prefetched if need_end_card else None,
            )

        return True

    async def _send_live_notification(
        self,
        room_id: str,
        status: str,
        state: LiveRoomState,
        prefetched_images: Optional[PrefetchImages] = None,
    ):
        """发送直播通知"""
        # 获取目标群组
        target_groups = self.config.live_monitor_mapping.get(room_id, [])
        target_users = self.config.live_monitor_user_mapping.get(room_id, [])
        if not target_groups and not target_users:
            logger.warning(f"房间 {room_id} 没有配置推送目标")
            return

        # 获取主播名称
        streamer_name = state.user_info.name if state.user_info else f"房间{room_id}"

        # 计算直播时长（仅关播时使用）
        duration_seconds = state.get_duration_seconds() if status == "end" else 0

        # 使用发送器发送通知
        await self._sender.send_notification(
            status=status,
            streamer_name=streamer_name,
            room_info=state.room_info,
            target_groups=target_groups,
            target_users=target_users,
            user_info=state.user_info,
            duration_seconds=duration_seconds,
            at_all_enabled=self.config.live_at_all.get(room_id, True),
            prefetched_images=prefetched_images,
        )

        asyncio.create_task(self._persist_state(room_id))

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
    global live_monitor_instance, _config_reload_registered

    if live_monitor_instance is not None:
        logger.warning("直播监控已在运行中")
        return

    config = Config.from_service()

    # 检查是否有配置的房间
    if not config.live_monitor_mapping:
        logger.warning("未配置任何直播间监控，跳过启动")
        return

    group_count = sum(len(groups) for groups in config.live_monitor_mapping.values())
    user_count = sum(len(users) for users in config.live_monitor_user_mapping.values())
    mode = "WebSocket+轮询备用" if config.use_websocket else "仅轮询"
    logger.info(
        f"准备启动直播监控: {len(config.live_monitor_mapping)} 个房间, "
        f"{group_count} 个群推送目标, {user_count} 个好友推送目标, "
        f"模式 {mode}, 间隔 {config.monitor_interval}秒"
    )

    try:
        # 创建监控实例
        live_monitor_instance = LiveMonitor(config)

        # 启动监控
        await live_monitor_instance.start_monitoring()

        if not _config_reload_registered:
            get_config_service().register_reload_callback(_on_config_reload)
            _config_reload_registered = True

        logger.info("B站直播监控已启动")

    except Exception as e:
        logger.error(f"启动直播监控失败: {e}")
        live_monitor_instance = None


async def stop_live_monitor():
    """停止直播监控"""
    global live_monitor_instance

    if not live_monitor_instance:
        return

    logger.info("正在停止直播监控...")

    try:
        await live_monitor_instance.stop_monitoring()
        live_monitor_instance = None
        logger.info("直播监控已完全停止")

    except Exception as e:
        logger.error(f"停止直播监控时出错: {e}")
        live_monitor_instance = None
