"""
UP主动态监控插件
监控B站UP主动态更新，并在指定群组发送通知
"""

from nonebot import get_driver
from nonebot.log import logger
from . import dynamic_monitor

# 注册生命周期事件
driver = get_driver()

@driver.on_bot_connect
async def _(bot):
    """机器人连接后开始监控"""
    logger.info(f"机器人 {bot.self_id} 已连接，开始初始化动态监控...")
    try:
        await dynamic_monitor.start_dynamic_monitor()
        logger.info("动态监控初始化完成")
    except Exception as e:
        logger.error(f"动态监控初始化失败: {e}")

@driver.on_bot_disconnect
async def _(bot):
    """机器人断开连接时停止监控"""
    logger.info(f"机器人 {bot.self_id} 断开连接，正在停止动态监控...")
    try:
        await dynamic_monitor.stop_dynamic_monitor()
        logger.info("动态监控已停止")
    except Exception as e:
        logger.error(f"动态监控停止失败: {e}")

@driver.on_shutdown
async def _():
    """应用关闭时确保监控完全停止"""
    logger.info("应用关闭，确保动态监控完全停止...")
    try:
        await dynamic_monitor.stop_dynamic_monitor()
        logger.info("动态监控已在应用关闭时完全停止")
    except Exception as e:
        logger.error(f"应用关闭时动态监控停止失败: {e}")

__plugin_meta__ = {
    "name": "UP主动态监控",
    "description": "监控B站UP主动态更新并在群组发送通知",
    "usage": "自动监控UP主动态更新",
    "version": "1.0.0",
    "author": "cyxcbot"
}