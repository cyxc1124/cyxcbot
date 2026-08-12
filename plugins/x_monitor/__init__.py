"""
X (Twitter) 监控插件
监控 X 博主新推文，并向配置的 QQ 群/好友推送通知（v1 仅自动推送）
"""

from nonebot import get_driver
from nonebot.log import logger

from shared.onebot.lifecycle import stop_monitor_if_no_bots

from . import x_monitor

driver = get_driver()


@driver.on_bot_connect
async def _(bot):
    """机器人连接后开始监控"""
    logger.info("机器人 {} 已连接，开始初始化 X 监控...", bot.self_id)
    try:
        await x_monitor.start_x_monitor()
        logger.info("X 监控初始化完成")
    except Exception:
        logger.opt(exception=True).error("X 监控初始化失败")


@driver.on_bot_disconnect
async def _(bot):
    """机器人断开连接时，仅在没有其他 Bot 在线时停止监控"""
    try:
        stopped = await stop_monitor_if_no_bots(
            x_monitor.stop_x_monitor,
            bot_self_id=bot.self_id,
            monitor_name="X 监控",
        )
        if stopped:
            logger.info("X 监控已停止")
    except Exception:
        logger.opt(exception=True).error("X 监控停止失败")


@driver.on_shutdown
async def _():
    """应用关闭时确保监控完全停止"""
    logger.info("应用关闭，确保 X 监控完全停止...")
    try:
        await x_monitor.stop_x_monitor()
        logger.info("X 监控已在应用关闭时完全停止")
    except Exception:
        logger.opt(exception=True).error("应用关闭时 X 监控停止失败")


__plugin_meta__ = {
    "name": "X 监控",
    "description": "监控 X (Twitter) 博主新推文并推送到 QQ 群/好友",
    "usage": "在 Web Admin 配置 Bearer Token、代理与监听博主后自动推送（v1 无群命令）",
    "version": "1.0.0",
    "author": "cyxcbot",
}
