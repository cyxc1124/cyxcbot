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

# 全局监控实例
dynamic_monitor_instance: Optional['DynamicMonitor'] = None


class DynamicMonitor:
    """UP主动态监控核心类"""

    def __init__(self, config: Config):
        self.config = config
        self.last_dynamic_ids: Dict[str, int] = {}  # UID -> 最后动态ID
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.fetcher: Optional[DynamicFetcher] = None
        self.sender: Optional[DynamicSender] = None

    async def start_monitoring(self):
        """启动监控"""
        self.is_running = True
        self.session = aiohttp.ClientSession()
        self.fetcher = DynamicFetcher(self.session)
        self.sender = DynamicSender(self.config.include_dynamic_details)
        logger.info("UP主动态监控已启动")

        # 初始化最后动态ID
        for uid in self.config.dynamic_monitor_mapping.keys():
            self.last_dynamic_ids[uid] = 0

        # 启动监控循环
        while self.is_running:
            try:
                await self._check_all_dynamics()
                await asyncio.sleep(self.config.monitor_interval)
            except Exception as e:
                logger.error(f"动态监控出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再试

    async def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        if self.session:
            await self.session.close()
        logger.info("UP主动态监控已停止")

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

        # 获取用户的动态列表
        dynamics = await self.fetcher.fetch_user_dynamics(uid)
        if not dynamics:
            logger.warning(f"获取UP主 {uid} 动态失败")
            return

        # 检查是否有新动态
        last_dynamic_id = self.last_dynamic_ids.get(uid, 0)
        new_dynamics = []

        for dynamic in dynamics:
            if dynamic.id > last_dynamic_id:
                new_dynamics.append(dynamic)

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

        # 构建通知消息
        message = self.sender.build_dynamic_message(dynamic)

        # 获取需要推送的群组列表
        group_ids = self.config.dynamic_monitor_mapping.get(uid, [])
        if not group_ids:
            logger.warning(f"UP主 {uid} 没有配置推送群组")
            return

        # 推送到每个群组
        await self.sender.send_to_groups(message, group_ids)

    def get_monitored_users(self) -> List[str]:
        """获取正在监控的UP主列表"""
        return list(self.config.dynamic_monitor_mapping.keys())

    def add_user(self, uid: str, groups: List[str]):
        """添加监控用户"""
        # TODO: 实现动态添加用户
        pass

    def remove_user(self, uid: str):
        """移除监控用户"""
        # TODO: 实现动态移除用户
        pass


# 插件启动和关闭函数
async def start_dynamic_monitor():
    """启动动态监控"""
    global dynamic_monitor_instance

    if dynamic_monitor_instance is None:
        from nonebot import get_plugin_config
        config = get_plugin_config(Config)

        # 检查是否有配置的用户
        if not config.dynamic_monitor_mapping:
            logger.warning("未配置任何UP主动态监控，跳过启动")
            return

        dynamic_monitor_instance = DynamicMonitor(config)
        await dynamic_monitor_instance.start_monitoring()


async def stop_dynamic_monitor():
    """停止动态监控"""
    global dynamic_monitor_instance

    if dynamic_monitor_instance:
        await dynamic_monitor_instance.stop_monitoring()
        dynamic_monitor_instance = None