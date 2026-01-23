"""
B站直播监控核心模块
负责监控直播间状态变化并发送通知
参考 blrec 的 LiveMonitor 设计

监控方式：
1. WebSocket 弹幕监听（主要）：实时监听 LIVE/PREPARING 命令
2. API 轮询（备用）：定时检查直播状态，防止 WebSocket 漏消息
"""

import asyncio
import aiohttp
from typing import Dict, Optional
from datetime import datetime
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from .config import Config
from .models import LiveRoomState
from .danmaku_client import DanmakuClient
from .sender import LiveNotificationSender
from utils.bilibili_api import LiveStatus, RoomInfo, UserInfo, api_manager


# 全局监控实例
live_monitor_instance: Optional['LiveMonitor'] = None


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
        # WebSocket 客户端: room_id -> DanmakuClient
        self._danmaku_clients: Dict[str, DanmakuClient] = {}
        # aiohttp session for WebSocket
        self._ws_session: Optional[aiohttp.ClientSession] = None
        # 通知发送器
        self._sender = LiveNotificationSender(include_room_info=config.include_room_info)
    
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
        
        logger.info(f"直播监控已初始化，监控房间数: {len(self.room_states)}")
    
    async def start_monitoring(self):
        """启动监控"""
        self.is_running = True
        
        # 初始化资源
        await self.init_resources()
        
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
            logger.info(f"直播监控已启动：WebSocket 实时监控 + API 轮询备用（间隔 {poll_interval}秒）")
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
            misfire_grace_time=60
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
        for room_id in self.room_states.keys():
            try:
                await self._start_single_danmaku_client(room_id)
            except Exception as e:
                logger.error(f"房间 {room_id} 弹幕客户端启动失败: {e}")
            # 避免同时连接过多
            await asyncio.sleep(1)
    
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
        
        self._danmaku_clients[room_id] = client
        await client.start()
        logger.info(f"房间 {room_id} WebSocket 监控已启动")
    
    async def _stop_danmaku_clients(self):
        """停止所有弹幕客户端"""
        for room_id, client in self._danmaku_clients.items():
            try:
                await client.stop()
                logger.debug(f"房间 {room_id} 弹幕客户端已停止")
            except Exception as e:
                logger.warning(f"停止房间 {room_id} 弹幕客户端时出错: {e}")
        self._danmaku_clients.clear()
        logger.info("所有 WebSocket 客户端已停止")
    
    async def _handle_live_signal(self, room_id: str):
        """处理开播信号（来自 WebSocket）"""
        logger.info(f"房间 {room_id} 收到开播信号")
        
        state = self.room_states.get(room_id)
        if not state:
            return
        
        # 获取最新房间信息
        room_info, user_info = await api_manager.get_room_and_user_info(int(room_id))
        
        if not room_info:
            logger.warning(f"房间 {room_id} 获取信息失败")
            return
        
        # 检查状态变化
        old_status = state.previous_status
        
        if old_status != LiveStatus.LIVE and room_info.live_status == LiveStatus.LIVE:
            # 确认是开播
            state.previous_status = LiveStatus.LIVE
            state.room_info = room_info
            state.user_info = user_info
            state.start_time = room_info.live_start_time or int(datetime.now().timestamp())
            
            streamer_name = user_info.name if user_info else f"房间{room_id}"
            logger.info(f"确认开播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(room_id, "start", state)
        else:
            # 更新状态但不发送通知（可能是重复信号或已经在直播中）
            state.room_info = room_info
            if user_info:
                state.user_info = user_info
    
    async def _handle_preparing_signal(self, room_id: str, round_status: Optional[int]):
        """处理关播信号（来自 WebSocket）"""
        logger.info(f"房间 {room_id} 收到关播信号 (round={round_status})")
        
        state = self.room_states.get(room_id)
        if not state:
            return
        
        # 获取最新房间信息
        room_info, user_info = await api_manager.get_room_and_user_info(int(room_id))
        
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
            
            streamer_name = state.user_info.name if state.user_info else f"房间{room_id}"
            logger.info(f"确认关播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(room_id, "end", state)
    
    async def _handle_room_change(self, room_id: str, data: dict):
        """处理房间信息变更"""
        state = self.room_states.get(room_id)
        if not state or not state.room_info:
            return
        
        # 更新标题等信息
        if 'title' in data:
            logger.debug(f"房间 {room_id} 标题变更: {data['title']}")
    
    async def _init_room_states(self):
        """初始化所有房间的状态（首次启动时）"""
        for room_id, state in self.room_states.items():
            try:
                room_info, user_info = await api_manager.get_room_and_user_info(int(room_id))
                
                if room_info:
                    # 初始化状态，不触发通知
                    state.room_info = room_info
                    state.user_info = user_info
                    state.previous_status = room_info.live_status
                    
                    if room_info.is_living():
                        state.start_time = room_info.live_start_time or int(datetime.now().timestamp())
                        streamer_name = user_info.name if user_info else f"房间{room_id}"
                        logger.info(f"房间 {room_id} ({streamer_name}) 当前正在直播")
                    else:
                        streamer_name = user_info.name if user_info else f"房间{room_id}"
                        logger.info(f"房间 {room_id} ({streamer_name}) 当前未开播")
                else:
                    logger.warning(f"无法获取房间 {room_id} 的初始状态")
                    
            except Exception as e:
                logger.error(f"初始化房间 {room_id} 状态失败: {e}")
            
            # 避免请求过快
            await asyncio.sleep(0.5)
    
    async def _check_all_rooms(self):
        """检查所有房间的直播状态"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return
        
        logger.debug(f"开始检查所有直播间状态，共 {len(self.room_states)} 个房间")
        
        for room_id in self.room_states.keys():
            try:
                await self._check_room_status(room_id)
            except Exception as e:
                logger.error(f"检查房间 {room_id} 状态失败: {e}")
            
            # 避免请求过快
            await asyncio.sleep(0.3)
        
        logger.debug("完成本次直播状态检查")
    
    async def _check_room_status(self, room_id: str):
        """检查单个房间的直播状态"""
        state = self.room_states.get(room_id)
        if not state:
            return
        
        # 获取最新的房间信息
        room_info, user_info = await api_manager.get_room_and_user_info(int(room_id))
        
        if not room_info:
            logger.warning(f"无法获取房间 {room_id} 的最新状态")
            return
        
        # 更新状态并检测变化
        is_live_began, is_live_ended = state.update_status(room_info, user_info)
        
        # 处理开播事件
        if is_live_began:
            streamer_name = state.user_info.name if state.user_info else f"房间{room_id}"
            logger.info(f"检测到开播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(room_id, "start", state)
        
        # 处理关播事件
        if is_live_ended:
            streamer_name = state.user_info.name if state.user_info else f"房间{room_id}"
            logger.info(f"检测到关播: {streamer_name} (房间 {room_id})")
            await self._send_live_notification(room_id, "end", state)
    
    async def _send_live_notification(self, room_id: str, status: str, state: LiveRoomState):
        """发送直播通知"""
        # 获取目标群组
        target_groups = self.config.live_monitor_mapping.get(room_id, [])
        if not target_groups:
            logger.warning(f"房间 {room_id} 没有配置目标群组")
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
            duration_seconds=duration_seconds
        )
    
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
    
    if live_monitor_instance is not None:
        logger.warning("直播监控已在运行中")
        return
    
    from nonebot import get_plugin_config
    config = get_plugin_config(Config)
    
    # 检查是否有配置的房间
    if not config.live_monitor_mapping:
        logger.warning("未配置任何直播间监控，跳过启动")
        return
    
    try:
        # 创建监控实例
        live_monitor_instance = LiveMonitor(config)
        
        # 启动监控
        await live_monitor_instance.start_monitoring()
        
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
