"""
UP主动态监控插件
监控B站UP主动态更新，并在指定群组发送通知
支持主动查询最新动态和置顶动态
"""

from nonebot import get_driver, on_message
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.rule import to_me
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11.message import Message
from . import dynamic_monitor
from .config import Config

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

# 创建消息处理器 - 支持@机器人和命令前缀
dynamic_command = on_message(priority=5)

@dynamic_command.handle()
async def handle_dynamic_commands(event: GroupMessageEvent):
    """处理动态查询命令"""
    message_text = event.get_plaintext().strip()
    logger.debug(f"收到群消息: {message_text}")

    # 获取配置
    from nonebot import get_plugin_config
    config = get_plugin_config(Config)

    # 获取群组ID
    group_id = str(event.group_id)

    # 查找该群对应的UP主
    uids = config.get_uids_by_group_id(group_id)
    if not uids:
        logger.debug(f"群组 {group_id} 未配置任何UP主动态监控")
        # 不回复，让其他处理器处理
        return

    # 检查动态监控实例是否运行 - 动态导入以获取最新的实例状态
    from .dynamic_monitor import dynamic_monitor_instance

    logger.debug(f"检查动态监控实例: instance={dynamic_monitor_instance is not None}, is_running={dynamic_monitor_instance.is_running if dynamic_monitor_instance else 'N/A'}")

    if not dynamic_monitor_instance:
        logger.debug("动态监控实例不存在")
        # 不回复，让其他处理器处理
        return

    # 注释掉 is_running 检查，因为后台任务可能在运行但标志位有问题
    # if not dynamic_monitor_instance.is_running:
    #     logger.debug("动态监控服务未运行")
    #     # 不回复，让其他处理器处理
    #     return

    # 检查是否是动态查询命令
    is_command = False

    # 检查是否是@机器人 + 命令
    if event.is_tome():
        if message_text in ["最新动态", "置顶动态"]:
            is_command = True
        # 移除@机器人的部分，检查剩余内容
        elif message_text.startswith("最新动态") or message_text.startswith("置顶动态"):
            is_command = True
        elif message_text.endswith("最新动态") or message_text.endswith("置顶动态"):
            is_command = True

    # 检查是否是命令前缀 + 命令
    elif any(message_text.startswith(prefix) for prefix in ["/", "!", "。", "."]):
        cmd_text = message_text[1:].strip()
        if cmd_text in ["最新动态", "置顶动态"]:
            is_command = True

    # 检查是否是纯文本命令（直接发送"最新动态"或"置顶动态"）
    elif message_text in ["最新动态", "置顶动态"]:
        is_command = True

    if not is_command:
        logger.debug(f"消息 '{message_text}' 不是动态查询命令")
        # 不是我们的命令，让其他处理器处理
        return

    try:
        logger.info(f"处理动态查询命令: {message_text} in group {group_id}")

        if "最新动态" in message_text:
            # 为每个UP主获取最新动态
            for uid in uids:
                try:
                    logger.info(f"为UP主 {uid} 获取最新动态")
                    await dynamic_monitor_instance.get_latest_dynamic(uid, group_id)
                    logger.info(f"UP主 {uid} 最新动态获取完成")
                except Exception as e:
                    logger.error(f"获取UP主 {uid} 最新动态失败: {e}")
                    import traceback
                    logger.error(f"最新动态详细错误信息: {traceback.format_exc()}")
                    try:
                        from nonebot import get_bot
                        bot = get_bot()
                        if bot:
                            await bot.send_group_msg(
                                group_id=int(group_id),
                                message=f"UP主 {uid} 查询失败，请稍后重试"
                            )
                            logger.info(f"已发送失败提示消息给UP主 {uid}")
                    except Exception as send_e:
                        logger.error(f"发送失败提示消息失败: {send_e}")

        elif "置顶动态" in message_text:
            # 为每个UP主获取置顶动态
            for uid in uids:
                try:
                    logger.info(f"为UP主 {uid} 获取置顶动态")
                    await dynamic_monitor_instance.get_pinned_dynamic(uid, group_id)
                    logger.info(f"UP主 {uid} 置顶动态获取完成")
                except Exception as e:
                    logger.error(f"获取UP主 {uid} 置顶动态失败: {e}")
                    import traceback
                    logger.error(f"置顶动态详细错误信息: {traceback.format_exc()}")
                    try:
                        from nonebot import get_bot
                        bot = get_bot()
                        if bot:
                            await bot.send_group_msg(
                                group_id=int(group_id),
                                message=f"UP主 {uid} 查询失败，请稍后重试"
                            )
                            logger.info(f"已发送失败提示消息给UP主 {uid}")
                    except Exception as send_e:
                        logger.error(f"发送失败提示消息失败: {send_e}")

        # 事件已处理，阻止继续传播

    except Exception as e:
        logger.error(f"处理动态查询命令失败: {e}")
        import traceback
        logger.error(f"全局异常详细错误信息: {traceback.format_exc()}")
        try:
            from nonebot import get_bot
            bot = get_bot()
            if bot:
                await bot.send_group_msg(
                    group_id=int(group_id),
                    message="系统错误，请稍后重试"
                )
        except Exception as send_e:
            logger.error(f"发送系统错误消息失败: {send_e}")

__plugin_meta__ = {
    "name": "UP主动态监控",
    "description": "监控B站UP主动态更新并在群组发送通知，支持主动查询",
    "usage": "自动监控UP主动态更新，发送'最新动态'或'置顶动态'可主动查询",
    "version": "1.1.0",
    "author": "cyxcbot"
}