"""
B站视频查询插件
查询UP主最新投稿视频

功能特点：
1. 响应用户命令查询UP主最新视频
2. 和动态监控共用 DYNAMIC_MONITOR_MAPPING 配置
3. 只在配置的群组中响应命令

命令：
- 最新视频: 查询该群配置的UP主的最新视频
- 最新投稿: 同上
"""

from nonebot import on_message
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent

from .config import Config
from .sender import VideoSender

__plugin_meta__ = {
    "name": "B站视频查询",
    "description": "查询UP主最新投稿视频，和动态监控共用配置",
    "usage": "在配置的群组中发送'最新视频'或'最新投稿'查询UP主最新投稿",
    "version": "1.0.0",
    "author": "cyxcbot"
}

# 全局发送器
video_sender = VideoSender()

# 创建消息处理器
video_command = on_message(priority=5, block=False)


@video_command.handle()
async def handle_video_commands(event: GroupMessageEvent):
    """处理视频查询命令"""
    message_text = event.get_plaintext().strip()
    logger.debug(f"收到群消息: {message_text}")

    from .config import get_config
    config = get_config()

    # 获取群组ID
    group_id = str(event.group_id)

    # 查找该群对应的UP主
    uids = config.get_uids_by_group_id(group_id)
    if not uids:
        logger.debug(f"群组 {group_id} 未配置任何UP主监控")
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
        logger.debug(f"消息 '{message_text}' 不是视频查询命令")
        return

    try:
        logger.info(f"处理视频查询命令: {message_text} in group {group_id}")

        from utils.bilibili_api import video_api_manager

        # 初始化API（如果未初始化）
        try:
            # 尝试调用，如果失败则初始化
            await video_api_manager.init(config.bilibili_cookie)
        except Exception:
            pass

        # 为每个UP主获取最新视频
        for uid in uids:
            try:
                logger.info(f"为UP主 {uid} 获取最新视频")

                # 获取最新5个视频
                videos = await video_api_manager.get_user_videos(int(uid), page=1, page_size=5)

                if videos:
                    # 构建消息
                    message = video_sender.build_video_message(videos)
                    # 发送到群组
                    await video_sender.send_to_group(group_id, message)
                    logger.info(f"UP主 {uid} 最新视频获取完成")
                else:
                    logger.warning(f"无法获取UP主 {uid} 的视频")
                    from nonebot import get_bot
                    bot = get_bot()
                    if bot:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f"无法获取UP主 {uid} 的视频，请检查UID是否正确"
                        )

            except Exception as e:
                logger.error(f"获取UP主 {uid} 最新视频失败: {e}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                try:
                    from nonebot import get_bot
                    bot = get_bot()
                    if bot:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f"UP主 {uid} 视频查询失败，请稍后重试"
                        )
                except Exception as send_e:
                    logger.error(f"发送失败提示消息失败: {send_e}")

    except Exception as e:
        logger.error(f"处理视频查询命令失败: {e}")
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
