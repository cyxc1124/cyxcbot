"""
直播通知消息发送模块
负责构建和发送直播开播/关播通知消息
参考 stream_notify 的推送方式实现
"""

from typing import List, Optional
from datetime import datetime
from nonebot import get_driver
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from utils.bilibili_api import RoomInfo, UserInfo


class LiveNotificationSender:
    """直播通知发送器"""
    
    def __init__(self, include_room_info: bool = True):
        self.include_room_info = include_room_info
    
    async def build_start_message(
        self,
        streamer_name: str,
        room_info: Optional[RoomInfo],
        user_info: Optional[UserInfo] = None,
        can_at_all: bool = False
    ) -> Message:
        """
        构建开播通知消息
        
        尝试生成卡片图片替代原有封面；
        卡片生成失败时自动回退为原有纯文本+封面通知。
        """
        message = Message()
        
        if can_at_all:
            message.append(MessageSegment.at("all"))
        else:
            message.append("📢 请关注直播动态！")

        message.append(f" {streamer_name} 开播啦！\n")
        message.append("\n")
        
        card_image = await self._try_generate_card(streamer_name, user_info, room_info)
        
        if card_image:
            try:
                message.append(MessageSegment.image(card_image))
                message.append("\n")
            except Exception as e:
                logger.warning(f"添加卡片图片到消息失败: {e}")
                card_image = None
        
        if self.include_room_info and room_info:
            if not card_image:
                message.append(f"标题：{room_info.title}\n")
                
                if room_info.live_start_time > 0:
                    start_time = datetime.fromtimestamp(room_info.live_start_time)
                    time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                    message.append(f"开播时间：{time_str}\n")
                    message.append("\n")
                
                if room_info.cover:
                    try:
                        message.append(MessageSegment.image(room_info.cover))
                        message.append("\n")
                    except Exception as e:
                        logger.warning(f"添加直播封面失败: {e}")
            
            message.append(f"{room_info.get_live_url()}")
        
        return message
    
    def build_end_message(
        self,
        streamer_name: str,
        duration_seconds: int = 0
    ) -> Message:
        message = Message()
        message.append("【下播提醒】\n")
        message.append(f"{streamer_name}下播啦！\n")
        
        if duration_seconds > 0:
            duration_str = self._format_duration(duration_seconds)
            message.append(f"直播时长：{duration_str}")
        
        return message
    
    def _format_duration(self, seconds: int) -> str:
        if seconds <= 0:
            return ""
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟{secs}秒"
        elif minutes > 0:
            return f"{minutes}分钟{secs}秒"
        else:
            return f"{secs}秒"
    
    async def _try_generate_card(
        self,
        streamer_name: str,
        user_info: Optional[UserInfo],
        room_info: Optional[RoomInfo],
    ) -> Optional[bytes]:
        """尝试生成卡片图片，失败返回 None（触发降级）"""
        try:
            from .card_generator import generate_live_start_card
            return await generate_live_start_card(
                streamer_name=streamer_name,
                user_info=user_info,
                room_info=room_info,
            )
        except Exception as e:
            logger.error(f"生成开播卡片失败，将降级为纯文本通知: {e}")
            return None
    
    async def check_admin_permission(self, bot: Bot, group_id: str) -> bool:
        try:
            bot_info = await bot.get_group_member_info(
                group_id=int(group_id),
                user_id=int(bot.self_id),
                no_cache=False
            )
            role = bot_info.get("role", "member")
            return role in ["admin", "owner"]
        except Exception as e:
            logger.warning(f"检查机器人管理员权限失败: {e}")
            return False
    
    async def send_notification(
        self,
        status: str,
        streamer_name: str,
        room_info: Optional[RoomInfo],
        target_groups: List[str],
        user_info: Optional[UserInfo] = None,
        duration_seconds: int = 0
    ):
        """
        发送直播通知到指定群组
        
        Args:
            status: 状态类型 ("start" 或 "end")
            streamer_name: 主播名称
            room_info: 房间信息对象
            target_groups: 目标群组ID列表
            user_info: 主播用户信息（头像等，开播卡片需要）
            duration_seconds: 直播时长（秒，仅关播时使用）
        """
        if not target_groups:
            logger.warning(f"没有配置目标群组，跳过发送通知")
            return
        
        logger.info(f"开始发送直播{status}通知 - 主播: {streamer_name}, 目标群组: {target_groups}")
        
        bots = get_driver().bots
        
        if not bots:
            logger.warning("没有可用的机器人实例")
            return
        
        for bot_id, bot in bots.items():
            if not isinstance(bot, Bot):
                continue
            
            logger.debug(f"使用机器人 {bot_id} 发送通知")
            
            for group_id in target_groups:
                try:
                    can_at_all = await self.check_admin_permission(bot, group_id)
                    
                    if status == "start":
                        message = await self.build_start_message(
                            streamer_name=streamer_name,
                            room_info=room_info,
                            user_info=user_info,
                            can_at_all=can_at_all
                        )
                    else:
                        message = self.build_end_message(
                            streamer_name=streamer_name,
                            duration_seconds=duration_seconds
                        )
                    
                    await bot.send_group_msg(
                        group_id=int(group_id),
                        message=message
                    )
                    logger.success(f"直播{status}通知已发送到群组 {group_id}")
                    
                except Exception as e:
                    logger.error(f"发送通知到群组 {group_id} 失败: {e}")
                    import traceback
                    logger.debug(f"错误详情: {traceback.format_exc()}")


notification_sender: Optional[LiveNotificationSender] = None


def get_sender(include_room_info: bool = True) -> LiveNotificationSender:
    """获取或创建发送器实例"""
    global notification_sender
    if notification_sender is None:
        notification_sender = LiveNotificationSender(
            include_room_info=include_room_info,
        )
    return notification_sender
