"""
UP主动态监控核心模块
负责协调各个组件进行动态监控
"""

from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from nonebot.adapters.onebot.v11.message import Message
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_session

from shared.config.service import get_config_service
from shared.db.models import DynamicMonitorState
from shared.monitor.check_cycle import CheckCycleLogger
from shared.monitor.poll_schedule import compute_dynamic_poll_schedule
from utils.bilibili_api import DynamicFetcher
from utils.screenshot import (
    close_screenshot_service,
    get_dynamic_screenshot,
    init_screenshot_service,
)

from .config import Config
from .sender import DynamicSender

# 全局监控实例
dynamic_monitor_instance: Optional["DynamicMonitor"] = None


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
        self._stagger_index = 0
        self._cycle_logger = CheckCycleLogger("动态监控")
        self.last_check_at: Optional[str] = None

    def _touch_last_check_at(self) -> None:
        self.last_check_at = datetime.now().isoformat(timespec="seconds")

    def _uid_list(self) -> List[str]:
        return list(self.config.dynamic_monitor_mapping.keys())

    def _schedule_poll_job(self) -> None:
        uid_list = self._uid_list()
        if not uid_list:
            return

        schedule = compute_dynamic_poll_schedule(
            len(uid_list),
            self.config.monitor_interval,
            use_stagger=self.config.use_stagger_poll,
        )

        if self.config.use_stagger_poll:
            tick = schedule["tick_interval_seconds"]
            callback = self._check_next_dynamic
            mode_label = "分散检查"
        else:
            tick = self.config.monitor_interval
            callback = self._check_all_dynamics
            mode_label = "批量检查"

        scheduler.add_job(
            callback,
            "interval",
            seconds=tick,
            id="dynamic_monitor_check",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
        )
        logger.info(
            f"动态监控调度({mode_label}): {len(uid_list)} 个UP主, "
            f"定时 {tick:.1f}秒, "
            f"每人周期约 {schedule['per_target_cycle_seconds']:.0f}秒, "
            f"峰值约 {schedule['requests_per_second_peak']:.2f} 次/秒"
        )
        if schedule.get("warning"):
            logger.warning(schedule["warning"])

    async def init_resources(self):
        """初始化资源"""
        self.session = aiohttp.ClientSession()
        self.fetcher = DynamicFetcher(self.session, self.config.bilibili_cookie)
        self.sender = DynamicSender(templates=self.config.message_templates)

        # 初始化置顶动态ID记录
        for uid in self.config.dynamic_monitor_mapping.keys():
            if uid not in self.pinned_dynamic_ids:
                self.pinned_dynamic_ids[uid] = None

        if self.config.enable_screenshot:
            await init_screenshot_service()
            logger.info("动态截图服务已启动")
        else:
            logger.info("动态截图已关闭（可在 Web Admin 设置中开启）")

        if not self.config.bilibili_cookie:
            logger.warning("动态监控: 未登录 B 站，动态可能无法获取")

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
        old_use_stagger = self.config.use_stagger_poll
        old_screenshot = self.config.enable_screenshot
        old_cookie = self.config.bilibili_cookie
        old_uids = set(self.config.dynamic_monitor_mapping.keys())
        self.config = Config.from_service()
        new_uids_set = set(self.config.dynamic_monitor_mapping.keys())

        if self.fetcher:
            self.fetcher.cookie = self.config.bilibili_cookie

        new_uids: list[str] = []
        for uid in self.config.dynamic_monitor_mapping.keys():
            if uid not in self.last_dynamic_ids:
                self.last_dynamic_ids[uid] = 0
                self.initialized_uids[uid] = False
                self.pinned_dynamic_ids[uid] = None
                new_uids.append(uid)

        if self.is_running:
            for uid in new_uids:
                try:
                    await self._check_user_dynamic(uid)
                except Exception as e:
                    logger.error(f"初始化UP主 {uid} 动态监控失败: {e}")

        if self.is_running and (
            old_interval != self.config.monitor_interval
            or old_use_stagger != self.config.use_stagger_poll
            or old_uids != new_uids_set
        ):
            if (
                old_uids != new_uids_set
                or old_use_stagger != self.config.use_stagger_poll
            ):
                self._stagger_index = 0
                self._cycle_logger.reset()
            self._schedule_poll_job()

        if old_screenshot != self.config.enable_screenshot:
            if self.config.enable_screenshot:
                await init_screenshot_service()
            else:
                await close_screenshot_service()
        elif (
            self.config.enable_screenshot and old_cookie != self.config.bilibili_cookie
        ):
            await close_screenshot_service()
            await init_screenshot_service()

        if self.sender:
            self.sender.templates = self.config.message_templates

        logger.info(
            f"动态监控配置已热重载: {len(self.config.dynamic_monitor_mapping)} 个UP主, "
            f"间隔 {self.config.monitor_interval}秒, "
            f"模式={'分散检查' if self.config.use_stagger_poll else '批量检查'}, "
            f"截图={'开启' if self.config.enable_screenshot else '关闭'}"
        )

    async def start_monitoring(self):
        """启动监控 - 使用APScheduler定时任务"""
        self.is_running = True

        # 初始化资源
        await self.init_resources()

        logger.info(
            f"UP主动态监控已启动，"
            f"{'分散检查' if self.config.use_stagger_poll else '批量检查'}模式，"
            f"目标周期: {self.config.monitor_interval}秒"
        )

        self._schedule_poll_job()
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

    async def _check_next_dynamic(self):
        """分散检查下一个 UP 主的动态 - 由 APScheduler 定时调用"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return

        uid_list = self._uid_list()
        if not uid_list:
            return

        if self._stagger_index >= len(uid_list):
            self._stagger_index = 0

        uid = uid_list[self._stagger_index]
        self._stagger_index = (self._stagger_index + 1) % len(uid_list)
        cycle_completed = self._stagger_index == 0

        try:
            ok = await self._check_user_dynamic(uid)
            if ok is False:
                self._cycle_logger.record_failure(uid)
            else:
                self._cycle_logger.record_success()
                self._touch_last_check_at()
        except Exception as e:
            self._cycle_logger.record_error(uid, e)

        if cycle_completed:
            self._cycle_logger.emit_summary()
            self._touch_last_check_at()

    async def _check_all_dynamics(self):
        """批量检查全部 UP 主的动态 - 由 APScheduler 定时调用"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return

        uid_list = self._uid_list()
        if not uid_list:
            return

        try:
            for uid in uid_list:
                try:
                    ok = await self._check_user_dynamic(uid)
                    if ok is False:
                        self._cycle_logger.record_failure(uid)
                    else:
                        self._cycle_logger.record_success()
                except Exception as e:
                    self._cycle_logger.record_error(uid, e)

            self._cycle_logger.emit_summary()
            self._touch_last_check_at()
        except Exception as e:
            logger.error(f"动态监控检查出错: {e}")

    async def run_manual_check(
        self, uids: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """检查指定或全部 UP 主的动态（手动触发时使用）。"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return {"checked": [], "failed": []}

        uid_list = uids if uids is not None else self._uid_list()
        cycle = CheckCycleLogger("动态监控（手动）")
        checked: List[str] = []
        failed: List[str] = []

        try:
            for uid in uid_list:
                try:
                    ok = await self._check_user_dynamic(uid)
                    if ok is False:
                        cycle.record_failure(uid)
                        failed.append(uid)
                    else:
                        cycle.record_success()
                        checked.append(uid)
                except Exception as e:
                    cycle.record_error(uid, e)
                    failed.append(uid)

            cycle.emit_summary(log_success_at_info=True)
            self._touch_last_check_at()
        except Exception as e:
            logger.error(f"动态监控检查出错: {e}")

        return {"checked": checked, "failed": failed}

    async def _check_user_dynamic(self, uid: str) -> bool:
        """检查单个UP主的动态，成功返回 True，拉取失败返回 False。"""
        logger.debug(f"检查UP主 {uid} 的动态")

        # 获取用户的动态列表，传递当前置顶动态ID用于比较
        current_pinned_id = self.pinned_dynamic_ids.get(uid)
        # 获取Cookie（如果配置了）
        cookie = self.config.bilibili_cookie if self.config.bilibili_cookie else None
        result = await self.fetcher.fetch_user_dynamics(uid, current_pinned_id, cookie)

        if not result:
            logger.debug(f"获取UP主 {uid} 动态失败")
            return False

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
                logger.info(
                    f"UP主 {uid} 首次监控，已记录最新动态ID: {self.last_dynamic_ids[uid]}"
                )
            else:
                logger.info(f"UP主 {uid} 首次监控，当前无动态")

            self.pinned_dynamic_ids[uid] = new_pinned_id
            if new_pinned_id:
                logger.info(f"UP主 {uid} 首次监控，已记录置顶动态ID: {new_pinned_id}")

            self.initialized_uids[uid] = True
            await self._persist_state(uid)
            return True

        # 处理置顶动态变化（只有在非首次启动时才推送置顶动态变化）
        if new_pinned_id != current_pinned_id:
            logger.info(
                f"UP主 {uid} 置顶动态已更新: {current_pinned_id} -> {new_pinned_id}"
            )
            self.pinned_dynamic_ids[uid] = new_pinned_id

            # 只有当前置顶动态ID存在且有变化时，才推送置顶动态通知
            if new_pinned_id and current_pinned_id is not None:
                # 查找置顶动态并推送
                pinned_dynamic = next(
                    (d for d in dynamics if d.id == new_pinned_id), None
                )
                if pinned_dynamic:
                    await self._send_dynamic_notification(
                        uid, pinned_dynamic, is_pinned=True
                    )

        # 如果有新动态，处理推送
        if new_dynamics:
            # 更新最后动态ID为最新的动态ID
            self.last_dynamic_ids[uid] = max(d.id for d in new_dynamics)

            # 对每个新动态进行推送
            for dynamic in sorted(new_dynamics, key=lambda x: x.timestamp):
                await self._send_dynamic_notification(uid, dynamic)

        if new_dynamics or new_pinned_id != current_pinned_id:
            await self._persist_state(uid)

        return True

    async def _fetch_dynamic_screenshot(self, dynamic_id: int) -> Optional[bytes]:
        """获取动态截图，未启用时直接返回 None"""
        if not self.config.enable_screenshot:
            return None
        try:
            screenshot_image, screenshot_error = await get_dynamic_screenshot(
                dynamic_id
            )
            if screenshot_error:
                logger.warning(f"获取动态{dynamic_id}截图失败: {screenshot_error}")
            return screenshot_image
        except Exception as e:
            logger.warning(f"截图服务异常: {e}")
            return None

    async def _send_dynamic_notification(
        self, uid: str, dynamic, is_pinned: bool = False
    ):
        """发送动态通知"""
        # 获取真实的用户名（只在需要推送时才获取）
        real_name = await self.fetcher._get_user_name_from_api(str(dynamic.uid))
        if real_name:
            dynamic.name = real_name
            logger.info(
                f"发现新动态: {dynamic.name} - {dynamic.get_type_description()}"
            )
        else:
            dynamic.name = f"UP主_{dynamic.uid}"
            logger.info(
                f"发现新动态: UP主_{dynamic.uid} - {dynamic.get_type_description()}"
            )

        screenshot_image = await self._fetch_dynamic_screenshot(dynamic.id)

        # 构建通知消息
        message = self.sender.build_dynamic_message(
            dynamic,
            screenshot_image,
            is_pinned,
            include_dynamic_media=not self.config.enable_screenshot,
        )

        # 获取需要推送的群组与好友
        group_ids = self.config.dynamic_monitor_mapping.get(uid, [])
        user_ids = self.config.dynamic_monitor_user_mapping.get(uid, [])
        if not group_ids and not user_ids:
            logger.warning(f"UP主 {uid} 没有配置推送目标")
            return

        at_all_enabled = self.config.dynamic_at_all.get(uid, False)
        await self.sender.send_to_groups(
            message, group_ids, at_all_enabled=at_all_enabled
        )
        await self.sender.send_to_users(message, user_ids)
        logger.info(
            f"动态通知已推送: uid={uid} dynamic_id={dynamic.id} "
            f"groups={len(group_ids)} users={len(user_ids)} pinned={is_pinned}"
        )

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
            await self.sender.send_to_groups(
                Message("该UP主暂无非置顶的动态"), [group_id]
            )
            return

        latest_dynamic = max(filtered_dynamics, key=lambda x: x.timestamp)
        logger.debug(
            f"UP主 {uid} 最新动态ID: {latest_dynamic.id}, 类型: {latest_dynamic.get_type_description()}"
        )

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

    group_count = sum(len(groups) for groups in config.dynamic_monitor_mapping.values())
    user_count = sum(
        len(users) for users in config.dynamic_monitor_user_mapping.values()
    )
    logger.info(
        f"准备启动动态监控: {len(config.dynamic_monitor_mapping)} 个UP主, "
        f"{group_count} 个群推送目标, {user_count} 个好友推送目标, "
        f"间隔 {config.monitor_interval}秒"
    )

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
