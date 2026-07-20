"""
UP主动态监控插件
监控B站UP主动态更新，并在指定群组发送通知
支持主动查询最新动态和置顶动态
"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.log import logger

from shared.config.command_aliases import match_plain
from shared.config.service import get_config_service
from shared.onebot.lifecycle import stop_monitor_if_no_bots

from . import (
    dynamic_extract,  # noqa: F401
    dynamic_monitor,
)
from .config import Config

# 注册生命周期事件
driver = get_driver()


@driver.on_bot_connect
async def _(bot):
    """机器人连接后开始监控"""
    logger.info("机器人 {} 已连接，开始初始化动态监控...", bot.self_id)
    try:
        await dynamic_monitor.start_dynamic_monitor()
        logger.info("动态监控初始化完成")
    except Exception:
        logger.opt(exception=True).error("动态监控初始化失败")


@driver.on_bot_disconnect
async def _(bot):
    """机器人断开连接时，仅在没有其他 Bot 在线时停止监控"""
    try:
        stopped = await stop_monitor_if_no_bots(
            dynamic_monitor.stop_dynamic_monitor,
            bot_self_id=bot.self_id,
            monitor_name="动态监控",
        )
        if stopped:
            logger.info("动态监控已停止")
    except Exception:
        logger.opt(exception=True).error("动态监控停止失败")


@driver.on_shutdown
async def _():
    """应用关闭时确保监控完全停止"""
    logger.info("应用关闭，确保动态监控完全停止...")
    try:
        await dynamic_monitor.stop_dynamic_monitor()
        logger.info("动态监控已在应用关闭时完全停止")
    except Exception:
        logger.opt(exception=True).error("应用关闭时动态监控停止失败")


# 创建消息处理器 - 支持@机器人和命令前缀
dynamic_command = on_message(priority=5, block=False)


@dynamic_command.handle()
async def handle_dynamic_commands(bot: Bot, event: GroupMessageEvent):
    """处理动态查询命令"""
    message_text = event.get_plaintext().strip()
    logger.debug("收到群消息: {}", message_text)

    config = Config.from_service()

    # 获取群组ID
    group_id = str(event.group_id)

    # 查找该群对应的UP主
    uids = config.get_uids_by_group_id(group_id)
    if not uids:
        logger.debug("群组 {} 未配置任何UP主动态监控", group_id)
        # 不回复，让其他处理器处理
        return

    # 检查动态监控实例是否运行 - 动态导入以获取最新的实例状态
    from .dynamic_monitor import dynamic_monitor_instance

    logger.debug(
        "检查动态监控实例: instance={}, is_running={}",
        dynamic_monitor_instance is not None,
        dynamic_monitor_instance.is_running if dynamic_monitor_instance else "N/A",
    )

    if not dynamic_monitor_instance:
        logger.debug("动态监控实例不存在")
        # 不回复，让其他处理器处理
        return

    # 注释掉 is_running 检查，因为后台任务可能在运行但标志位有问题
    # if not dynamic_monitor_instance.is_running:
    #     logger.debug("动态监控服务未运行")
    #     # 不回复，让其他处理器处理
    #     return

    # 检查是否是动态查询命令（触发词可在 Web Admin 设置 → 命令 中自定义）
    command_aliases = get_config_service().get_snapshot().command_aliases
    is_tome = event.is_tome()
    is_latest = match_plain(
        message_text, "dynamic_query_latest", command_aliases, is_tome=is_tome
    )
    is_pinned = match_plain(
        message_text, "dynamic_query_pinned", command_aliases, is_tome=is_tome
    )

    if not (is_latest or is_pinned):
        logger.debug("消息 '{}' 不是动态查询命令", message_text)
        # 不是我们的命令，让其他处理器处理
        return

    try:
        logger.info("处理动态查询命令: {} in group {}", message_text, group_id)

        if is_latest:
            # 为每个UP主获取最新动态
            for uid in uids:
                try:
                    logger.info("为UP主 {} 获取最新动态", uid)
                    await dynamic_monitor_instance.get_latest_dynamic(uid, group_id)
                    logger.info("UP主 {} 最新动态获取完成", uid)
                except Exception:
                    logger.opt(exception=True).error("获取UP主 {} 最新动态失败", uid)
                    try:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f"UP主 {uid} 查询失败，请稍后重试",
                        )
                        logger.info("已发送失败提示消息给UP主 {}", uid)
                    except Exception:
                        logger.opt(exception=True).error("发送失败提示消息失败")

        elif is_pinned:
            # 为每个UP主获取置顶动态
            for uid in uids:
                try:
                    logger.info("为UP主 {} 获取置顶动态", uid)
                    await dynamic_monitor_instance.get_pinned_dynamic(uid, group_id)
                    logger.info("UP主 {} 置顶动态获取完成", uid)
                except Exception:
                    logger.opt(exception=True).error("获取UP主 {} 置顶动态失败", uid)
                    try:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f"UP主 {uid} 查询失败，请稍后重试",
                        )
                        logger.info("已发送失败提示消息给UP主 {}", uid)
                    except Exception:
                        logger.opt(exception=True).error("发送失败提示消息失败")

        # 事件已处理，阻止继续传播

    except Exception:
        logger.opt(exception=True).error("处理动态查询命令失败")
        try:
            await bot.send_group_msg(
                group_id=int(group_id), message="系统错误，请稍后重试"
            )
        except Exception:
            logger.opt(exception=True).error("发送系统错误消息失败")


__plugin_meta__ = {
    "name": "UP主动态监控",
    "description": "监控B站UP主动态更新并在群组发送通知，支持主动查询与动态图片提取",
    "usage": "发送'最新动态'或'置顶动态'可主动查询；发送'#提取{动态ID}'可提取动态内全部图片",
    "version": "1.2.0",
    "author": "cyxcbot",
}
