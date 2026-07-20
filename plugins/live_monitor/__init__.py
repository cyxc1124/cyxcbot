"""
B 站直播监控插件：WebSocket 弹幕 + API 轮询，开播/下播推送。

配置见 Web Admin → 直播监控 / 设置；详见 plugins/live_monitor/README.md。
"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.config.command_aliases import match_command_arg, match_plain
from shared.config.service import get_config_service
from shared.onebot.lifecycle import stop_monitor_if_no_bots

from . import live_monitor as live_monitor_mod
from .config import Config
from .live_monitor import start_live_monitor, stop_live_monitor

__plugin_meta__ = PluginMetadata(
    name="B站直播监控",
    description="主动监控B站直播间开播/关播状态并发送通知",
    usage="""
在 Web Admin 配置房间映射后自动监控。

命令：
- 直播状态 [房间号]: 查询指定房间的直播状态
- 监控列表: 列出当前群监控的房间
""",
    type="application",
    homepage="https://github.com/cyxc1124/cyxcbot",
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
    """机器人断开连接时，仅在没有其他 Bot 在线时停止监控"""
    try:
        stopped = await stop_monitor_if_no_bots(
            stop_live_monitor,
            bot_self_id=bot.self_id,
            monitor_name="直播监控",
        )
        if stopped:
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


# 查询直播状态命令（触发词可在 Web Admin 设置 → 命令 中自定义）
live_status_cmd = on_message(priority=10, block=False)


@live_status_cmd.handle()
async def handle_live_status(bot: Bot, event: GroupMessageEvent):
    """处理直播状态查询命令"""
    text = event.get_plaintext().strip()
    snap = get_config_service().get_snapshot()
    room_id_arg = match_command_arg(text, "live_status", snap.command_aliases)
    if room_id_arg is None:
        return
    room_id = room_id_arg.strip()
    logger.info(f"直播状态查询: group={event.group_id} room={room_id or '(未指定)'}")

    if not room_id:
        await live_status_cmd.finish("请指定房间号，例如：直播状态 12345")

    # 验证房间号格式
    if not room_id.isdigit():
        await live_status_cmd.finish("房间号格式错误，请输入数字")

    await live_status_cmd.send(f"正在查询房间 {room_id} 的直播状态...")

    try:
        if live_monitor_mod.live_monitor_instance:
            result = await live_monitor_mod.live_monitor_instance.check_room_now(
                room_id
            )
        else:
            # 监控实例未启动：使用独立 session 临时查询，避免关闭监控正在使用的共享 api_manager
            import aiohttp

            from utils.bilibili_api import LiveApi

            cookie = Config.from_service().bilibili_cookie
            async with aiohttp.ClientSession() as session:
                temp_api = LiveApi(session, cookie)
                room_info, user_info = await temp_api.get_room_and_user_info(
                    int(room_id)
                )

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


# 列出监控房间命令（触发词可在 Web Admin 设置 → 命令 中自定义）
list_monitor_cmd = on_message(priority=10, block=False)


@list_monitor_cmd.handle()
async def handle_list_monitor(bot: Bot, event: GroupMessageEvent):
    """列出当前监控的房间"""
    text = event.get_plaintext().strip()
    snap = get_config_service().get_snapshot()
    if not match_plain(
        text, "live_monitor_list", snap.command_aliases, is_tome=event.is_tome()
    ):
        return

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
    instance = live_monitor_mod.live_monitor_instance
    for room_id in monitored_rooms:
        try:
            if instance and room_id in instance.room_states:
                state = instance.room_states[room_id]
                name = state.user_info.name if state.user_info else f"房间{room_id}"
                is_living = state.room_info.is_living() if state.room_info else False
            else:
                name = f"房间{room_id}"
                is_living = False

            status_emoji = "🔴" if is_living else "⚫"
            message += f"{status_emoji} {name} ({room_id})\n"
        except AttributeError, TypeError, KeyError:
            message += f"⚫ 房间{room_id}\n"

    await list_monitor_cmd.finish(message)
