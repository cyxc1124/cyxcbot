"""
UP主动态监控核心模块
负责协调各个组件进行动态监控
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional
from nonebot.log import logger

from .config import Config
from .fetcher import DynamicFetcher
from .sender import DynamicSender
from .screenshot import init_screenshot_service, close_screenshot_service, get_dynamic_screenshot

# 全局监控实例和任务
dynamic_monitor_instance: Optional['DynamicMonitor'] = None
_monitoring_task: Optional[asyncio.Task] = None


class DynamicMonitor:
    """UP主动态监控核心类"""

    def __init__(self, config: Config):
        self.config = config
        self.last_dynamic_ids: Dict[str, int] = {}  # UID -> 最后动态ID
        self.pinned_dynamic_ids: Dict[str, str] = {}  # UID -> 当前置顶动态ID
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.fetcher: Optional[DynamicFetcher] = None
        self.sender: Optional[DynamicSender] = None

    async def start_monitoring(self):
        """启动监控"""
        self.is_running = True
        self.session = aiohttp.ClientSession()
        self.fetcher = DynamicFetcher(self.session)
        self.sender = DynamicSender(self.config.enable_dynamic_screenshot)

        # 初始化置顶动态ID记录
        for uid in self.config.dynamic_monitor_mapping.keys():
            if uid not in self.pinned_dynamic_ids:
                self.pinned_dynamic_ids[uid] = None

        # 如果启用了截图功能，初始化截图服务
        if self.config.enable_dynamic_screenshot:
            await init_screenshot_service()
            logger.info("动态截图服务已启动")

        logger.info(f"UP主动态监控已启动，使用RSSHub: {self.config.rsshub_base_url}")

        # 初始化最后动态ID
        for uid in self.config.dynamic_monitor_mapping.keys():
            self.last_dynamic_ids[uid] = 0

        try:
            # 启动监控循环
            while self.is_running:
                try:
                    # 检查是否被要求停止
                    if not self.is_running:
                        break

                    await self._check_all_dynamics()
                    await asyncio.sleep(self.config.monitor_interval)

                except asyncio.CancelledError:
                    # 处理取消信号
                    logger.info("动态监控收到取消信号，正在停止...")
                    self.is_running = False
                    break

                except Exception as e:
                    if self.is_running:  # 只在仍在运行时记录错误
                        logger.error(f"动态监控出错: {e}")
                        try:
                            await asyncio.sleep(60)
                        except asyncio.CancelledError:
                            self.is_running = False
                            break

        finally:
            logger.info("动态监控循环已结束")
            # 确保资源被清理
            await self._cleanup_resources()

    async def _cleanup_resources(self):
        """清理资源"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
            if self.config.enable_dynamic_screenshot:
                await close_screenshot_service()
        except Exception as e:
            logger.warning(f"清理资源时出错: {e}")

    async def stop_monitoring(self):
        """停止监控"""
        logger.info("正在停止UP主动态监控...")
        self.is_running = False
        # 注意：资源清理由start_monitoring的finally块处理
        logger.info("UP主动态监控停止信号已发送")

    async def _check_all_dynamics(self):
        """检查所有UP主的动态"""
        for uid in self.config.dynamic_monitor_mapping.keys():
            try:
                await self._check_user_dynamic(uid)
            except Exception as e:
                logger.error(f"检查UP主 {uid} 动态失败: {e}")

    async def _check_user_dynamic(self, uid: str):
        """检查单个UP主的动态"""
        logger.debug(f"检查UP主 {uid} 的动态")

        # 获取用户的动态列表，传递当前置顶动态ID用于比较
        current_pinned_id = self.pinned_dynamic_ids.get(uid)
        result = await self.fetcher.fetch_user_dynamics(uid, current_pinned_id)

        if not result:
            logger.warning(f"获取UP主 {uid} 动态失败")
            return

        dynamics, new_pinned_id = result

        # 检查是否有新动态
        last_dynamic_id = self.last_dynamic_ids.get(uid, 0)
        new_dynamics = []

        for dynamic in dynamics:
            if dynamic.id > last_dynamic_id:
                new_dynamics.append(dynamic)

        # 如果是第一次检查该用户（last_dynamic_id为0），只记录状态，不推送
        if last_dynamic_id == 0:
            # 记录最新的动态ID作为基准点
            if new_dynamics:
                self.last_dynamic_ids[uid] = max(d.id for d in new_dynamics)
                logger.info(f"UP主 {uid} 首次监控，已记录最新动态ID: {self.last_dynamic_ids[uid]}")

            # 记录当前的置顶动态ID作为基准点
            self.pinned_dynamic_ids[uid] = new_pinned_id
            if new_pinned_id:
                logger.info(f"UP主 {uid} 首次监控，已记录置顶动态ID: {new_pinned_id}")

            return

        # 处理置顶动态变化（只有在非首次启动时才推送置顶动态变化）
        if new_pinned_id != current_pinned_id:
            logger.info(f"UP主 {uid} 置顶动态已更新: {current_pinned_id} -> {new_pinned_id}")
            self.pinned_dynamic_ids[uid] = new_pinned_id

            # 只有当前置顶动态ID存在且有变化时，才推送置顶动态通知
            if new_pinned_id and current_pinned_id is not None:
                # 查找置顶动态并推送
                pinned_dynamic = next((d for d in dynamics if str(d.id) == new_pinned_id), None)
                if pinned_dynamic:
                    await self._send_dynamic_notification(uid, pinned_dynamic)

        # 如果有新动态，处理推送
        if new_dynamics:
            # 更新最后动态ID为最新的动态ID
            self.last_dynamic_ids[uid] = max(d.id for d in new_dynamics)

            # 对每个新动态进行推送
            for dynamic in sorted(new_dynamics, key=lambda x: x.timestamp):
                await self._send_dynamic_notification(uid, dynamic)

    async def _send_dynamic_notification(self, uid: str, dynamic):
        """发送动态通知"""
        logger.info(f"发现新动态: {dynamic.name} - {dynamic.get_type_description()}")

        # 获取动态截图（如果启用了截图功能）
        screenshot_image = None
        if self.config.enable_dynamic_screenshot:
            try:
                screenshot_image, screenshot_error = await get_dynamic_screenshot(dynamic.id)
                if screenshot_error:
                    logger.warning(f"获取动态{dynamic.id}截图失败: {screenshot_error}")
            except Exception as e:
                logger.warning(f"截图服务异常: {e}")

        # 构建通知消息
        message = self.sender.build_dynamic_message(dynamic, screenshot_image)

        # 获取需要推送的群组列表
        group_ids = self.config.dynamic_monitor_mapping.get(uid, [])
        if not group_ids:
            logger.warning(f"UP主 {uid} 没有配置推送群组")
            return

        # 推送到每个群组
        await self.sender.send_to_groups(message, group_ids)



# 插件启动和关闭函数
async def start_dynamic_monitor():
    """启动动态监控"""
    global dynamic_monitor_instance, _monitoring_task

    if dynamic_monitor_instance is not None:
        logger.warning("动态监控已在运行中")
        return

    from nonebot import get_plugin_config
    config = get_plugin_config(Config)

    # 检查是否有配置的用户
    if not config.dynamic_monitor_mapping:
        logger.warning("未配置任何UP主动态监控，跳过启动")
        return

    try:
        # 创建监控实例
        dynamic_monitor_instance = DynamicMonitor(config)

        # 创建监控任务
        _monitoring_task = asyncio.create_task(
            dynamic_monitor_instance.start_monitoring()
        )

        # 添加任务完成的回调
        def task_done_callback(task):
            try:
                if task.exception():
                    logger.error(f"动态监控任务异常结束: {task.exception()}")
                else:
                    logger.info("动态监控任务正常结束")
            except Exception as e:
                logger.error(f"处理任务完成回调时出错: {e}")

        _monitoring_task.add_done_callback(task_done_callback)

        logger.info("UP主动态监控任务已创建并启动")

    except Exception as e:
        logger.error(f"启动动态监控失败: {e}")
        dynamic_monitor_instance = None
        if _monitoring_task:
            _monitoring_task.cancel()
            _monitoring_task = None


async def stop_dynamic_monitor():
    """停止动态监控"""
    global dynamic_monitor_instance, _monitoring_task

    if not dynamic_monitor_instance:
        return

    logger.info("正在停止动态监控...")

    try:
        # 首先设置实例的运行标志为False
        if dynamic_monitor_instance:
            dynamic_monitor_instance.is_running = False

        # 取消监控任务
        if _monitoring_task and not _monitoring_task.done():
            _monitoring_task.cancel()
            try:
                # 等待任务完成，但设置超时避免无限等待
                await asyncio.wait_for(_monitoring_task, timeout=5.0)
                logger.info("动态监控任务已正常结束")
            except asyncio.TimeoutError:
                logger.warning("动态监控任务取消超时")
            except asyncio.CancelledError:
                logger.info("动态监控任务已取消")
            except Exception as e:
                logger.error(f"等待任务结束时出错: {e}")

        # 停止监控实例
        if dynamic_monitor_instance:
            await dynamic_monitor_instance.stop_monitoring()
            dynamic_monitor_instance = None

        _monitoring_task = None
        logger.info("动态监控已完全停止")

    except Exception as e:
        logger.error(f"停止动态监控时出错: {e}")
        # 即使出错也要清理资源
        dynamic_monitor_instance = None
        _monitoring_task = None