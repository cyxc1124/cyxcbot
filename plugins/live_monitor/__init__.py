"""
B站直播监控插件
主动监控B站直播间开播/关播状态并发送通知

功能特点：
1. 定时轮询B站API检测直播状态
2. 自动发送开播/关播通知
3. 支持多房间多群组配置
4. 开播时支持@全体成员（需要管理员权限）

配置说明：
- LIVE_MONITOR_MAPPING: 房间号-群组映射，格式: {"房间号": ["群号1", "群号2"], ...}
- LIVE_MONITOR_INTERVAL: 检查间隔（秒），默认60秒，最小30秒
- LIVE_MONITOR_INCLUDE_INFO: 是否包含详细信息，默认true
- B 站 Cookie: 在 Web Admin 账号设置中登录
"""

from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

from .config import Config
from .live_monitor import live_monitor_instance, start_live_monitor, stop_live_monitor

__plugin_meta__ = PluginMetadata(
    name="B站直播监控",
    description="主动监控B站直播间开播/关播状态并发送通知",
    usage="""
配置环境变量后自动启动监控：
- LIVE_MONITOR_MAPPING: 房间号-群组映射
- LIVE_MONITOR_INTERVAL: 检查间隔（秒）

命令：
- 直播状态 [房间号]: 查询指定房间的直播状态
""",
    type="application",
    homepage="https://github.com/your-repo",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

driver = get_driver()


@driver.on_bot_connect
async def _(bot):
    """机器人连接后开始监控"""
    logger.info(f"机器人 {bot.self_id} 已连接，开始初始化直播监控...")
    try:
        await start_live_monitor()
        logger.info("直播监控初始化完成")
    except Exception as e:
        logger.error(f"直播监控初始化失败: {e}")


@driver.on_bot_disconnect
async def _(bot):
    """机器人断开连接时停止监控"""
    logger.info(f"机器人 {bot.self_id} 断开连接，正在停止直播监控...")
    try:
        await stop_live_monitor()
        logger.info("直播监控已停止")
    except Exception as e:
        logger.error(f"直播监控停止失败: {e}")


@driver.on_shutdown
async def _():
    """应用关闭时确保监控完全停止"""
    logger.info("应用关闭，确保直播监控完全停止...")
    try:
        await stop_live_monitor()
        logger.info("直播监控已在应用关闭时完全停止")
    except Exception as e:
        logger.error(f"应用关闭时直播监控停止失败: {e}")


# 查询直播状态命令
live_status_cmd = on_command(
    "直播状态", aliases={"查直播", "live"}, priority=10, block=True
)


@live_status_cmd.handle()
async def handle_live_status(
    bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()
):
    """处理直播状态查询命令"""
    room_id = args.extract_plain_text().strip()
    logger.info(f"直播状态查询: group={event.group_id} room={room_id or '(未指定)'}")

    if not room_id:
        await live_status_cmd.finish("请指定房间号，例如：直播状态 12345")

    # 验证房间号格式
    if not room_id.isdigit():
        await live_status_cmd.finish("房间号格式错误，请输入数字")

    await live_status_cmd.send(f"正在查询房间 {room_id} 的直播状态...")

    try:
        if live_monitor_instance:
            result = await live_monitor_instance.check_room_now(room_id)
        else:
            # 如果监控实例未启动，临时获取状态
            from utils.bilibili_api import api_manager

            await api_manager.init()
            room_info, user_info = await api_manager.get_room_and_user_info(
                int(room_id)
            )
            await api_manager.close()

            if room_info:
                result = {
                    "room_id": room_info.room_id,
                    "streamer_name": user_info.name if user_info else f"房间{room_id}",
                    "title": room_info.title,
                    "is_living": room_info.is_living(),
                    "live_status": room_info.live_status.name,
                    "area": f"{room_info.parent_area_name} - {room_info.area_name}",
                    "online": room_info.online,
                }
            else:
                result = None

        if result:
            status_emoji = "🔴" if result["is_living"] else "⚫"
            status_text = "直播中" if result["is_living"] else "未开播"

            message = f"{status_emoji} {result['streamer_name']}\n"
            message += f"状态：{status_text}\n"
            message += f"房间号：{result['room_id']}\n"

            if result["is_living"]:
                message += f"标题：{result['title']}\n"
                message += f"分区：{result['area']}\n"
                message += f"人气：{result['online']}\n"
                message += f"直播间：https://live.bilibili.com/{result['room_id']}"

            await live_status_cmd.finish(message)
        else:
            await live_status_cmd.finish(
                f"无法获取房间 {room_id} 的信息，请检查房间号是否正确"
            )

    except Exception as e:
        logger.error(f"查询直播状态失败: {e}")
        await live_status_cmd.finish(f"查询失败：{str(e)}")


# 列出监控房间命令
list_monitor_cmd = on_command(
    "监控列表", aliases={"直播监控列表"}, priority=10, block=True
)


@list_monitor_cmd.handle()
async def handle_list_monitor(bot: Bot, event: GroupMessageEvent):
    """列出当前监控的房间"""
    group_id = str(event.group_id)
    config = Config.from_service()

    # 找出当前群组监控的房间
    monitored_rooms = []
    for room_id, groups in config.live_monitor_mapping.items():
        if group_id in groups:
            monitored_rooms.append(room_id)

    if not monitored_rooms:
        await list_monitor_cmd.finish("当前群组没有配置任何直播间监控")

    message = f"📺 当前群组监控的直播间 ({len(monitored_rooms)} 个):\n"

    # 获取各房间状态
    for room_id in monitored_rooms:
        try:
            if live_monitor_instance and room_id in live_monitor_instance.room_states:
                state = live_monitor_instance.room_states[room_id]
                name = state.user_info.name if state.user_info else f"房间{room_id}"
                is_living = state.room_info.is_living() if state.room_info else False
            else:
                name = f"房间{room_id}"
                is_living = False

            status_emoji = "🔴" if is_living else "⚫"
            message += f"{status_emoji} {name} ({room_id})\n"
        except (AttributeError, TypeError, KeyError):
            message += f"⚫ 房间{room_id}\n"

    await list_monitor_cmd.finish(message)
