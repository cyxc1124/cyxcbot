"""
UP主动态监控核心模块
负责协调各个组件进行动态监控
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional
from nonebot.log import logger
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from .config import Config
from utils.bilibili_api import DynamicFetcher
from .sender import DynamicSender
from utils.screenshot import init_screenshot_service, close_screenshot_service, get_dynamic_screenshot

# 全局监控实例和任务
dynamic_monitor_instance: Optional['DynamicMonitor'] = None
_monitoring_task: Optional[asyncio.Task] = None


class DynamicMonitor:
    """UP主动态监控核心类"""

    def __init__(self, config: Config):
        self.config = config
        self.last_dynamic_ids: Dict[str, int] = {}  # UID -> 最后动态ID
        self.pinned_dynamic_ids: Dict[str, Optional[int]] = {}  # UID -> 当前置顶动态ID
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.fetcher: Optional[DynamicFetcher] = None
        self.sender: Optional[DynamicSender] = None

    async def start_monitoring(self):
        """启动监控"""
        self.is_running = True
        self.session = aiohttp.ClientSession()
        self.fetcher = DynamicFetcher(self.session, self.config.bilibili_cookie)
        self.sender = DynamicSender(self.config.enable_dynamic_screenshot)

        # 初始化置顶动态ID记录
        for uid in self.config.dynamic_monitor_mapping.keys():
            if uid not in self.pinned_dynamic_ids:
                self.pinned_dynamic_ids[uid] = None

        # 如果启用了截图功能，初始化截图服务
        if self.config.enable_dynamic_screenshot:
            await init_screenshot_service()
            logger.info("动态截图服务已启动")

        logger.info(f"UP主动态监控已启动，直接调用B站API，监控间隔: {self.config.monitor_interval}秒")

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
        logger.debug(f"开始检查所有UP主动态，共 {len(self.config.dynamic_monitor_mapping)} 个用户")
        for uid in self.config.dynamic_monitor_mapping.keys():
            try:
                await self._check_user_dynamic(uid)
            except Exception as e:
                logger.error(f"检查UP主 {uid} 动态失败: {e}")
        logger.debug(f"完成本次动态检查，将在 {self.config.monitor_interval} 秒后进行下次检查")

    async def _check_user_dynamic(self, uid: str):
        """检查单个UP主的动态"""
        logger.debug(f"检查UP主 {uid} 的动态")

        # 获取用户的动态列表，传递当前置顶动态ID用于比较
        current_pinned_id = self.pinned_dynamic_ids.get(uid)
        # 获取Cookie（如果配置了）
        cookie = self.config.bilibili_cookie if self.config.bilibili_cookie else None
        result = await self.fetcher.fetch_user_dynamics(uid, current_pinned_id, cookie)

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
                pinned_dynamic = next((d for d in dynamics if d.id == new_pinned_id), None)
                if pinned_dynamic:
                    await self._send_dynamic_notification(uid, pinned_dynamic, is_pinned=True)

        # 如果有新动态，处理推送
        if new_dynamics:
            # 更新最后动态ID为最新的动态ID
            self.last_dynamic_ids[uid] = max(d.id for d in new_dynamics)

            # 对每个新动态进行推送
            for dynamic in sorted(new_dynamics, key=lambda x: x.timestamp):
                await self._send_dynamic_notification(uid, dynamic)

    async def _send_dynamic_notification(self, uid: str, dynamic, is_pinned: bool = False):
        """发送动态通知"""
        # 获取真实的用户名（只在需要推送时才获取）
        real_name = await self.fetcher._get_user_name_from_api(str(dynamic.uid))
        if real_name:
            dynamic.name = real_name
            logger.info(f"发现新动态: {dynamic.name} - {dynamic.get_type_description()}")
        else:
            dynamic.name = f"UP主_{dynamic.uid}"
            logger.info(f"发现新动态: UP主_{dynamic.uid} - {dynamic.get_type_description()}")

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
        message = self.sender.build_dynamic_message(dynamic, screenshot_image, is_pinned)

        # 获取需要推送的群组列表
        group_ids = self.config.dynamic_monitor_mapping.get(uid, [])
        if not group_ids:
            logger.warning(f"UP主 {uid} 没有配置推送群组")
            return

        # 推送到每个群组
        await self.sender.send_to_groups(message, group_ids)

    async def get_latest_dynamic(self, uid: str, group_id: str):
        """获取并发送指定UP主的最新动态"""
        logger.info(f"主动获取UP主 {uid} 的最新动态")

        # 获取用户的动态列表
        cookie = self.config.bilibili_cookie if self.config.bilibili_cookie else None
        logger.debug(f"开始获取UP主 {uid} 的动态数据")
        result = await self.fetcher.fetch_user_dynamics(uid, None, cookie)
        logger.debug(f"获取UP主 {uid} 的动态数据完成: {result is not None}")

        if not result:
            logger.warning(f"获取UP主 {uid} 动态失败")
            raise Exception(f"无法获取UP主 {uid} 的动态数据")

        dynamics, _ = result
        logger.debug(f"UP主 {uid} 动态数量: {len(dynamics)}")

        if not dynamics:
            logger.info(f"UP主 {uid} 没有动态")
            await self.sender.send_to_groups(Message("该UP主暂无动态"), [group_id])
            return

        # 过滤掉置顶动态和直播动态，获取最新的动态（按时间戳排序）
        # 注意：直播动态已经在fetcher中被过滤，这里主要过滤置顶动态
        filtered_dynamics = [d for d in dynamics if not d.is_pinned and d.type != 16]
        if not filtered_dynamics:
            logger.info(f"UP主 {uid} 没有非置顶非直播动态")
            await self.sender.send_to_groups(Message("该UP主暂无非置顶的动态"), [group_id])
            return

        latest_dynamic = max(filtered_dynamics, key=lambda x: x.timestamp)
        logger.debug(f"UP主 {uid} 最新动态ID: {latest_dynamic.id}, 类型: {latest_dynamic.get_type_description()}")

        # 获取动态截图（如果启用了截图功能）
        screenshot_image = None
        if self.config.enable_dynamic_screenshot:
            try:
                screenshot_image, screenshot_error = await get_dynamic_screenshot(latest_dynamic.id)
                if screenshot_error:
                    logger.warning(f"获取动态{latest_dynamic.id}截图失败: {screenshot_error}")
            except Exception as e:
                logger.warning(f"截图服务异常: {e}")

        # 获取真实的用户名
        real_name = await self.fetcher._get_user_name_from_api(str(latest_dynamic.uid))
        if real_name:
            latest_dynamic.name = real_name
        else:
            latest_dynamic.name = f"UP主_{latest_dynamic.uid}"

        # 构建主动查询的消息（包含截图）
        logger.debug(f"开始构建UP主 {uid} 的主动查询消息")

        # 获取用户名
        real_name = await self.fetcher._get_user_name_from_api(str(latest_dynamic.uid))
        if real_name:
            latest_dynamic.name = real_name
        else:
            latest_dynamic.name = f"UP主_{latest_dynamic.uid}"

        # 使用统一的消息构建方法
        message = self.sender.build_dynamic_message(
            latest_dynamic,
            screenshot_image,
            is_pinned=False,
            is_query=True,
            query_type="latest"
        )

        logger.debug(f"主动查询消息构建完成，开始发送到群组 {group_id}")

        # 发送到指定群组
        await self.sender.send_to_groups(message, [group_id])
        logger.info(f"已发送UP主 {uid} 的最新动态查询结果到群组 {group_id}")

    async def get_pinned_dynamic(self, uid: str, group_id: str):
        """获取并发送指定UP主的置顶动态"""
        logger.info(f"主动获取UP主 {uid} 的置顶动态")

        # 获取用户的动态列表
        cookie = self.config.bilibili_cookie if self.config.bilibili_cookie else None
        logger.debug(f"开始获取UP主 {uid} 的动态数据")
        result = await self.fetcher.fetch_user_dynamics(uid, None, cookie)
        logger.debug(f"获取UP主 {uid} 的动态数据完成: {result is not None}")

        if not result:
            logger.warning(f"获取UP主 {uid} 动态失败")
            raise Exception(f"无法获取UP主 {uid} 的动态数据")

        dynamics, pinned_id = result

        if not pinned_id:
            logger.info(f"UP主 {uid} 没有置顶动态")
            await self.sender.send_to_groups(Message("该UP主暂无置顶动态"), [group_id])
            return

        # 查找置顶动态
        pinned_dynamic = next((d for d in dynamics if d.id == pinned_id), None)
        if not pinned_dynamic:
            logger.warning(f"未找到UP主 {uid} 的置顶动态 {pinned_id}")
            raise Exception(f"未找到UP主 {uid} 的置顶动态")

        # 获取动态截图（如果启用了截图功能）
        screenshot_image = None
        if self.config.enable_dynamic_screenshot:
            try:
                screenshot_image, screenshot_error = await get_dynamic_screenshot(pinned_dynamic.id)
                if screenshot_error:
                    logger.warning(f"获取动态{pinned_dynamic.id}截图失败: {screenshot_error}")
            except Exception as e:
                logger.warning(f"截图服务异常: {e}")

        # 获取用户名
        real_name = await self.fetcher._get_user_name_from_api(str(pinned_dynamic.uid))
        if real_name:
            pinned_dynamic.name = real_name
        else:
            pinned_dynamic.name = f"UP主_{pinned_dynamic.uid}"

        # 构建主动查询的消息（包含截图）
        logger.debug(f"开始构建UP主 {uid} 的置顶动态主动查询消息")

        # 使用统一的消息构建方法
        message = self.sender.build_dynamic_message(
            pinned_dynamic,
            screenshot_image,
            is_pinned=False,
            is_query=True,
            query_type="pinned"
        )

        logger.debug(f"置顶动态主动查询消息构建完成，开始发送到群组 {group_id}")

        # 发送到指定群组
        await self.sender.send_to_groups(message, [group_id])
        logger.info(f"已发送UP主 {uid} 的置顶动态查询结果到群组 {group_id}")



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