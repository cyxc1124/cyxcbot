"""
B站直播监控数据模型
提供监控专用的状态类
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from utils.bilibili_api import LiveStatus, RoomInfo, UserInfo


@dataclass
class LiveRoomState:
    """直播间状态（用于监控）"""
    room_id: int
    room_info: Optional[RoomInfo] = None
    user_info: Optional[UserInfo] = None
    previous_status: LiveStatus = LiveStatus.PREPARING
    start_time: int = 0  # 记录的开播时间戳
    
    def update_status(self, new_room_info: RoomInfo, new_user_info: Optional[UserInfo] = None) -> tuple[bool, bool]:
        """
        更新状态并返回状态变化
        返回: (是否开播, 是否关播)
        """
        is_live_began = False
        is_live_ended = False
        
        old_status = self.previous_status
        new_status = new_room_info.live_status
        
        # 检测状态变化
        if old_status != LiveStatus.LIVE and new_status == LiveStatus.LIVE:
            # 开播
            is_live_began = True
            self.start_time = new_room_info.live_start_time or int(datetime.now().timestamp())
        elif old_status == LiveStatus.LIVE and new_status != LiveStatus.LIVE:
            # 关播
            is_live_ended = True
        
        # 更新状态
        self.previous_status = new_status
        self.room_info = new_room_info
        if new_user_info:
            self.user_info = new_user_info
        
        return is_live_began, is_live_ended
    
    def get_duration_seconds(self) -> int:
        """获取直播时长（秒）"""
        if self.start_time > 0:
            return int(datetime.now().timestamp()) - self.start_time
        return 0
    
    def format_duration(self) -> str:
        """格式化直播时长"""
        seconds = self.get_duration_seconds()
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
