"""
UP主动态监控插件
监控B站UP主动态更新，并在指定群组发送通知
"""

from nonebot import get_driver
from . import dynamic_monitor

# 注册生命周期事件
driver = get_driver()

@driver.on_startup
async def _():
    """插件启动时开始监控"""
    await dynamic_monitor.start_dynamic_monitor()

@driver.on_shutdown
async def _():
    """插件关闭时停止监控"""
    await dynamic_monitor.stop_dynamic_monitor()

__plugin_meta__ = {
    "name": "UP主动态监控",
    "description": "监控B站UP主动态更新并在群组发送通知",
    "usage": "自动监控UP主动态更新",
    "version": "1.0.0",
    "author": "cyxcbot"
}