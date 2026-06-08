"""
UP主动态监控核心模块
负责协调各个组件进行动态监控
"""

import aiohttp
from typing import Dict, List, Optional
from nonebot.log import logger
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_session

from .config import Config
from utils.bilibili_api import DynamicFetcher
from .sender import DynamicSender
from utils.screenshot import init_screenshot_service, close_screenshot_service, get_dynamic_screenshot
from shared.audit.service import write_audit
from shared.config.service import get_config_service
from shared.db.enums import AuditAction
from shared.db.models import DynamicMonitorState

# 全局监控实例
dynamic_monitor_instance: Optional['DynamicMonitor'] = None


class DynamicMonitor:
    """UP主动态监控核心类"""

    def __init__(self, config: Config):
        self.config = config
        self.last_dynamic_ids: Dict[str, int] = {}  # UID -> 最后动态ID
        self.initialized_uids: Dict[str, bool] = {}  # UID -> 是否已完成首次基准记录
        self.pinned_dynamic_ids: Dict[str, Optional[int]] = {}  # UID -> 当前置顶动态ID
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.fetcher: Optional[DynamicFetcher] = None
        self.sender: Optional[DynamicSender] = None

    async def init_resources(self):
        """初始化资源"""
        self.session = aiohttp.ClientSession()
        self.fetcher = DynamicFetcher(self.session, self.config.bilibili_cookie)
        self.sender = DynamicSender()

        # 初始化置顶动态ID记录
        for uid in self.config.dynamic_monitor_mapping.keys():
            if uid not in self.pinned_dynamic_ids:
                self.pinned_dynamic_ids[uid] = None

        if self.config.enable_screenshot:
            await init_screenshot_service()
            logger.info("动态截图服务已启动")
        else:
            logger.info("动态截图已禁用（DYNAMIC_ENABLE_SCREENSHOT=false）")

        await self._load_persisted_states()

    async def _load_persisted_states(self):
        """从 DB 恢复监控状态"""
        for uid in self.config.dynamic_monitor_mapping.keys():
            if uid not in self.pinned_dynamic_ids:
                self.pinned_dynamic_ids[uid] = None

        session = get_session()
        async with session.begin():
            for uid in self.config.dynamic_monitor_mapping.keys():
                row = await session.get(DynamicMonitorState, uid)
                if row:
                    self.last_dynamic_ids[uid] = row.last_dynamic_id
                    self.initialized_uids[uid] = row.initialized
                    self.pinned_dynamic_ids[uid] = row.pinned_dynamic_id
                else:
                    self.last_dynamic_ids[uid] = 0
                    self.initialized_uids[uid] = False

    async def _persist_state(self, uid: str):
        """持久化单个 UID 的监控状态"""
        session = get_session()
        async with session.begin():
            row = await session.get(DynamicMonitorState, uid)
            if not row:
                row = DynamicMonitorState(uid=uid)
                session.add(row)
            row.last_dynamic_id = self.last_dynamic_ids.get(uid, 0)
            row.initialized = self.initialized_uids.get(uid, False)
            row.pinned_dynamic_id = self.pinned_dynamic_ids.get(uid)

    async def reload_config(self):
        """热重载配置并调整调度任务"""
        old_interval = self.config.monitor_interval
        old_screenshot = self.config.enable_screenshot
        self.config = Config.from_service()

        if self.fetcher:
            self.fetcher.cookie = self.config.bilibili_cookie

        for uid in self.config.dynamic_monitor_mapping.keys():
            if uid not in self.last_dynamic_ids:
                self.last_dynamic_ids[uid] = 0
                self.initialized_uids[uid] = False
                self.pinned_dynamic_ids[uid] = None

        if self.is_running and old_interval != self.config.monitor_interval:
            scheduler.add_job(
                self._check_all_dynamics,
                "interval",
                seconds=self.config.monitor_interval,
                id="dynamic_monitor_check",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=60,
            )
            logger.info(f"动态监控间隔已更新为 {self.config.monitor_interval}秒")

        if old_screenshot != self.config.enable_screenshot:
            if self.config.enable_screenshot:
                await init_screenshot_service()
            else:
                await close_screenshot_service()

    async def start_monitoring(self):
        """启动监控 - 使用APScheduler定时任务"""
        self.is_running = True
        
        # 初始化资源
        await self.init_resources()
        
        logger.info(f"UP主动态监控已启动，直接调用B站API，监控间隔: {self.config.monitor_interval}秒")

        # 使用APScheduler添加定时任务
        scheduler.add_job(
            self._check_all_dynamics,
            "interval",
            seconds=self.config.monitor_interval,
            id="dynamic_monitor_check",
            replace_existing=True,
            max_instances=1,  # 确保同一时间只有一个任务在执行
            misfire_grace_time=60  # 允许60秒的容错时间
        )
        
        logger.info("动态监控定时任务已添加到调度器")

    async def _cleanup_resources(self):
        """清理资源"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
            if self.config.enable_screenshot:
                await close_screenshot_service()
        except Exception as e:
            logger.warning(f"清理资源时出错: {e}")

    async def stop_monitoring(self):
        """停止监控"""
        logger.info("正在停止UP主动态监控...")
        self.is_running = False
        
        # 移除定时任务
        try:
            scheduler.remove_job("dynamic_monitor_check")
            logger.info("动态监控定时任务已从调度器移除")
        except Exception as e:
            logger.warning(f"移除定时任务时出错: {e}")
        
        # 清理资源
        await self._cleanup_resources()
        logger.info("UP主动态监控已完全停止")

    async def _check_all_dynamics(self):
        """检查所有UP主的动态 - 由APScheduler定时调用"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return
            
        try:
            logger.debug(f"开始检查所有UP主动态，共 {len(self.config.dynamic_monitor_mapping)} 个用户")
            for uid in self.config.dynamic_monitor_mapping.keys():
                try:
                    await self._check_user_dynamic(uid)
                except Exception as e:
                    logger.error(f"检查UP主 {uid} 动态失败: {e}")
            logger.debug(f"完成本次动态检查")
        except Exception as e:
            logger.error(f"动态监控检查出错: {e}")

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

        # 首次检查只记录基准状态，不推送（避免启动时刷屏）
        # 注意：不能用 last_dynamic_id == 0 判断，无动态用户的基准 ID 也会一直是 0
        if not self.initialized_uids.get(uid, False):
            if dynamics:
                self.last_dynamic_ids[uid] = max(d.id for d in dynamics)
                logger.info(f"UP主 {uid} 首次监控，已记录最新动态ID: {self.last_dynamic_ids[uid]}")
            else:
                logger.info(f"UP主 {uid} 首次监控，当前无动态")

            self.pinned_dynamic_ids[uid] = new_pinned_id
            if new_pinned_id:
                logger.info(f"UP主 {uid} 首次监控，已记录置顶动态ID: {new_pinned_id}")

            self.initialized_uids[uid] = True
            await self._persist_state(uid)
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

        if new_dynamics or new_pinned_id != current_pinned_id:
            await self._persist_state(uid)

    async def _fetch_dynamic_screenshot(self, dynamic_id: int) -> Optional[bytes]:
        """获取动态截图，未启用时直接返回 None"""
        if not self.config.enable_screenshot:
            return None
        try:
            screenshot_image, screenshot_error = await get_dynamic_screenshot(dynamic_id)
            if screenshot_error:
                logger.warning(f"获取动态{dynamic_id}截图失败: {screenshot_error}")
            return screenshot_image
        except Exception as e:
            logger.warning(f"截图服务异常: {e}")
            return None

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

        screenshot_image = await self._fetch_dynamic_screenshot(dynamic.id)

        # 构建通知消息
        message = self.sender.build_dynamic_message(
            dynamic,
            screenshot_image,
            is_pinned,
            include_dynamic_media=not self.config.enable_screenshot,
        )

        # 获取需要推送的群组列表
        group_ids = self.config.dynamic_monitor_mapping.get(uid, [])
        if not group_ids:
            logger.warning(f"UP主 {uid} 没有配置推送群组")
            return

        # 推送到每个群组
        at_all_enabled = self.config.dynamic_at_all.get(uid, False)
        await self.sender.send_to_groups(message, group_ids, at_all_enabled=at_all_enabled)

        try:
            await write_audit(
                AuditAction.DYNAMIC_PUSH,
                details=get_config_service().serialize_details({
                    "uid": uid,
                    "dynamic_id": dynamic.id,
                    "is_pinned": is_pinned,
                    "groups": group_ids,
                }),
            )
        except Exception as exc:
            logger.warning(f"写入动态推送审计日志失败: {exc}")

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

        screenshot_image = await self._fetch_dynamic_screenshot(latest_dynamic.id)

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
            query_type="latest",
            include_dynamic_media=not self.config.enable_screenshot,
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

        screenshot_image = await self._fetch_dynamic_screenshot(pinned_dynamic.id)

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
            query_type="pinned",
            include_dynamic_media=not self.config.enable_screenshot,
        )

        logger.debug(f"置顶动态主动查询消息构建完成，开始发送到群组 {group_id}")

        # 发送到指定群组
        await self.sender.send_to_groups(message, [group_id])
        logger.info(f"已发送UP主 {uid} 的置顶动态查询结果到群组 {group_id}")



# 插件启动和关闭函数
async def start_dynamic_monitor():
    """启动动态监控"""
    global dynamic_monitor_instance

    if dynamic_monitor_instance is not None:
        logger.warning("动态监控已在运行中")
        return

    config = Config.from_service()

    # 检查是否有配置的用户
    if not config.dynamic_monitor_mapping:
        logger.warning("未配置任何UP主动态监控，跳过启动")
        return

    try:
        # 创建监控实例
        dynamic_monitor_instance = DynamicMonitor(config)

        # 启动监控（会添加APScheduler定时任务）
        await dynamic_monitor_instance.start_monitoring()

        async def _on_config_reload(_snapshot):
            if dynamic_monitor_instance:
                await dynamic_monitor_instance.reload_config()

        get_config_service().register_reload_callback(_on_config_reload)

        logger.info("UP主动态监控已启动")

    except Exception as e:
        logger.error(f"启动动态监控失败: {e}")
        dynamic_monitor_instance = None


async def stop_dynamic_monitor():
    """停止动态监控"""
    global dynamic_monitor_instance

    if not dynamic_monitor_instance:
        return

    logger.info("正在停止动态监控...")

    try:
        # 停止监控实例（会移除APScheduler定时任务并清理资源）
        await dynamic_monitor_instance.stop_monitoring()
        dynamic_monitor_instance = None
        logger.info("动态监控已完全停止")

    except Exception as e:
        logger.error(f"停止动态监控时出错: {e}")
        # 即使出错也要清理资源
        dynamic_monitor_instance = None