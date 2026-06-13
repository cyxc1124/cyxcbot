"""
B站直播监控数据模型
提供监控专用的状态类
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from utils.bilibili_api import LiveStatus, RoomInfo, UserInfo


@dataclass
class LiveRoomState:
    """直播间状态（用于监控）"""

    room_id: int
    room_info: Optional[RoomInfo] = None
    user_info: Optional[UserInfo] = None
    previous_status: LiveStatus = LiveStatus.PREPARING
    start_time: int = 0  # 记录的开播时间戳
    pending_start: bool = False
    pending_end: bool = False
    pending_start_groups: List[str] = field(default_factory=list)
    pending_start_users: List[str] = field(default_factory=list)
    pending_end_groups: List[str] = field(default_factory=list)
    pending_end_users: List[str] = field(default_factory=list)

    def clear_pending_start(self) -> None:
        self.pending_start = False
        self.pending_start_groups = []
        self.pending_start_users = []

    def clear_pending_end(self) -> None:
        self.pending_end = False
        self.pending_end_groups = []
        self.pending_end_users = []

    def detect_status_change(
        self, new_room_info: RoomInfo
    ) -> tuple[bool, bool, LiveStatus, int]:
        """
        检测状态变化，不修改 previous_status。
        返回: (是否开播, 是否关播, 新状态, 开播时间戳)
        """
        is_live_began = False
        is_live_ended = False

        old_status = self.previous_status
        new_status = new_room_info.live_status
        start_time = self.start_time

        if old_status != LiveStatus.LIVE and new_status == LiveStatus.LIVE:
            is_live_began = True
            start_time = new_room_info.live_start_time or int(
                datetime.now().timestamp()
            )
        elif old_status == LiveStatus.LIVE and new_status != LiveStatus.LIVE:
            is_live_ended = True

        return is_live_began, is_live_ended, new_status, start_time

    def sync_observed_status(
        self,
        new_room_info: RoomInfo,
        new_status: LiveStatus,
        *,
        new_user_info: Optional[UserInfo] = None,
        start_time: Optional[int] = None,
    ) -> None:
        """同步房间观测状态，与通知投递结果解耦。"""
        self.previous_status = new_status
        self.room_info = new_room_info
        if new_user_info:
            self.user_info = new_user_info
        if start_time is not None:
            self.start_time = start_time

    def apply_status(
        self,
        new_room_info: RoomInfo,
        new_status: LiveStatus,
        *,
        new_user_info: Optional[UserInfo] = None,
        start_time: Optional[int] = None,
    ) -> None:
        """兼容旧调用方，语义同 sync_observed_status。"""
        self.sync_observed_status(
            new_room_info,
            new_status,
            new_user_info=new_user_info,
            start_time=start_time,
        )

    def update_status(
        self, new_room_info: RoomInfo, new_user_info: Optional[UserInfo] = None
    ) -> tuple[bool, bool]:
        """
        更新状态并返回状态变化
        返回: (是否开播, 是否关播)
        """
        is_live_began, is_live_ended, new_status, start_time = (
            self.detect_status_change(new_room_info)
        )
        self.sync_observed_status(
            new_room_info,
            new_status,
            new_user_info=new_user_info,
            start_time=start_time if is_live_began else None,
        )
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
