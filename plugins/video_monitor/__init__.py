"""
B站视频查询插件
查询UP主最新投稿视频

功能特点：
1. 响应用户命令查询UP主最新视频
2. 和动态监控共用订阅映射配置
3. 只在配置的群组中响应命令

命令：
- 最新视频: 查询该群配置的UP主的最新视频
- 最新投稿: 同上
"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.log import logger

from .config import get_cached_config, reload_config
from .sender import VideoSender

__plugin_meta__ = {
    "name": "B站视频查询",
    "description": "查询UP主最新投稿视频，和动态监控共用配置",
    "usage": "在配置的群组中发送'最新视频'或'最新投稿'查询UP主最新投稿",
    "version": "1.0.0",
    "author": "cyxcbot",
}

driver = get_driver()

# 全局发送器
video_sender = VideoSender()

# 创建消息处理器
video_command = on_message(priority=5, block=False)


@driver.on_startup
async def _video_monitor_startup() -> None:
    config = get_cached_config()
    uid_count = len(config.dynamic_monitor_mapping)
    logger.info("视频查询插件已就绪: 监控映射含 {} 个UP主", uid_count)
    if not config.bilibili_cookie:
        logger.warning("视频查询: 未配置 B 站 Cookie，视频接口可能受限")


async def _on_config_reload(_snapshot) -> None:
    config = reload_config()
    logger.info(
        "视频查询: 配置已热重载, 监控映射含 {} 个UP主",
        len(config.dynamic_monitor_mapping),
    )


def _register_config_reload() -> None:
    try:
        from shared.config.service import get_config_service

        get_config_service().register_reload_callback(_on_config_reload)
    except Exception as exc:
        logger.warning("视频查询: 配置热重载注册失败: {}", exc)


_register_config_reload()


@video_command.handle()
async def handle_video_commands(event: GroupMessageEvent):
    """处理视频查询命令"""
    message_text = event.get_plaintext().strip()
    logger.debug("收到群消息: {}", message_text)

    config = get_cached_config()

    # 获取群组ID
    group_id = str(event.group_id)

    # 查找该群对应的UP主
    uids = config.get_uids_by_group_id(group_id)
    if not uids:
        logger.debug("群组 {} 未配置任何UP主监控", group_id)
        return

    # 检查是否是视频查询命令
    is_command = False

    # 检查是否是@机器人 + 命令
    if event.is_tome():
        if message_text in ["最新视频", "最新投稿"]:
            is_command = True
        elif message_text.startswith("最新视频") or message_text.startswith("最新投稿"):
            is_command = True
        elif message_text.endswith("最新视频") or message_text.endswith("最新投稿"):
            is_command = True

    # 检查是否是命令前缀 + 命令
    elif any(message_text.startswith(prefix) for prefix in ["/", "!", "。", "."]):
        cmd_text = message_text[1:].strip()
        if cmd_text in ["最新视频", "最新投稿"]:
            is_command = True

    # 检查是否是纯文本命令
    elif message_text in ["最新视频", "最新投稿"]:
        is_command = True

    if not is_command:
        logger.debug("消息 '{}' 不是视频查询命令", message_text)
        return

    try:
        logger.info("处理视频查询命令: {} in group {}", message_text, group_id)

        from utils.bilibili_api import video_api_manager

        # 初始化API（如果未初始化）
        try:
            await video_api_manager.init(config.bilibili_cookie)
        except Exception:
            pass

        # 为每个UP主获取最新视频
        for uid in uids:
            try:
                logger.info("为UP主 {} 获取最新视频", uid)

                videos = await video_api_manager.get_user_videos(
                    int(uid), page=1, page_size=5
                )

                if videos:
                    message = video_sender.build_video_message(videos)
                    await video_sender.send_to_group(group_id, message)
                    logger.info("UP主 {} 最新视频已回复到群 {}", uid, group_id)
                else:
                    logger.warning("无法获取UP主 {} 的视频", uid)
                    from nonebot import get_bot

                    bot = get_bot()
                    if bot:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f"无法获取UP主 {uid} 的视频，请检查UID是否正确",
                        )

            except Exception:
                logger.opt(exception=True).error("获取UP主 {} 最新视频失败", uid)
                try:
                    from nonebot import get_bot

                    bot = get_bot()
                    if bot:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f"UP主 {uid} 视频查询失败，请稍后重试",
                        )
                except Exception:
                    logger.opt(exception=True).error("发送失败提示消息失败")

    except Exception:
        logger.opt(exception=True).error("处理视频查询命令失败")
        try:
            from nonebot import get_bot

            bot = get_bot()
            if bot:
                await bot.send_group_msg(
                    group_id=int(group_id), message="系统错误，请稍后重试"
                )
        except Exception:
            logger.opt(exception=True).error("发送系统错误消息失败")
