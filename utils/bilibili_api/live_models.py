"""
B站直播数据模型
提供直播状态、房间信息、用户信息等通用数据模型
"""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class LiveStatus(IntEnum):
    """直播状态枚举"""

    PREPARING = 0  # 未开播/准备中
    LIVE = 1  # 直播中
    ROUND = 2  # 轮播中


@dataclass
class RoomInfo:
    """直播间信息"""

    uid: int  # 主播UID
    room_id: int  # 房间号
    short_room_id: int  # 短房间号
    area_id: int  # 分区ID
    area_name: str  # 分区名称
    parent_area_id: int  # 父分区ID
    parent_area_name: str  # 父分区名称
    live_status: LiveStatus  # 直播状态
    live_start_time: int  # 开播时间戳（秒）
    online: int  # 在线人数/人气值
    title: str  # 直播间标题
    cover: str  # 封面图URL
    tags: str = ""  # 标签
    description: str = ""  # 描述

    @classmethod
    def from_api_data(cls, data: dict) -> "RoomInfo":
        """从API响应数据创建RoomInfo对象"""
        # 处理开播时间
        live_start_time = data.get("live_start_time", 0)
        if not live_start_time:
            live_time = data.get("live_time")
            if live_time and live_time != "0000-00-00 00:00:00":
                try:
                    dt = datetime.fromisoformat(live_time)
                    live_start_time = int(dt.timestamp())
                except (ValueError, TypeError, OverflowError):
                    live_start_time = 0

        # 处理封面URL
        cover = data.get("cover") or data.get("user_cover", "")
        if cover and not cover.startswith("http"):
            cover = "https:" + cover

        return cls(
            uid=data.get("uid", 0),
            room_id=int(data.get("room_id", 0)),
            short_room_id=int(data.get("short_id", 0)),
            area_id=data.get("area_id", 0),
            area_name=data.get("area_name", ""),
            parent_area_id=data.get("parent_area_id", 0),
            parent_area_name=data.get("parent_area_name", ""),
            live_status=LiveStatus(data.get("live_status", 0)),
            live_start_time=live_start_time,
            online=int(data.get("online", 0)),
            title=data.get("title", ""),
            cover=cover,
            tags=data.get("tags", ""),
            description=data.get("description", ""),
        )

    def is_living(self) -> bool:
        """判断是否正在直播"""
        return self.live_status == LiveStatus.LIVE

    def get_live_url(self) -> str:
        """获取直播间链接"""
        return f"https://live.bilibili.com/{self.room_id}"

    def to_dict(self) -> dict:
        """转换为字典（用于消息发送等场景）"""
        return {
            "uid": self.uid,
            "room_id": self.room_id,
            "short_room_id": self.short_room_id,
            "area_id": self.area_id,
            "area_name": self.area_name,
            "parent_area_id": self.parent_area_id,
            "parent_area_name": self.parent_area_name,
            "live_status": self.live_status,
            "live_start_time": self.live_start_time,
            "online": self.online,
            "title": self.title,
            "cover": self.cover,
            "tags": self.tags,
            "description": self.description,
        }


@dataclass
class UserInfo:
    """主播用户信息"""

    uid: int  # 用户UID
    name: str  # 用户名
    face: str  # 头像URL
    gender: str = ""  # 性别

    @classmethod
    def from_api_data(cls, data: dict) -> "UserInfo":
        """从API响应数据创建UserInfo对象"""
        # 支持多种数据结构
        if "anchor_info" in data:
            # 从 getInfoByRoom 接口获取
            base_info = data["anchor_info"]["base_info"]
            room_info = data["room_info"]
            return cls(
                uid=room_info.get("uid", 0),
                name=base_info.get("uname", ""),
                face=cls._ensure_https(base_info.get("face", "")),
                gender=base_info.get("gender", ""),
            )
        elif "card" in data:
            # 从 app API 获取
            card = data["card"]
            return cls(
                uid=card.get("mid", 0),
                name=card.get("name", ""),
                face=cls._ensure_https(card.get("face", "")),
                gender=card.get("sex", ""),
            )
        else:
            # 从 web API 获取
            return cls(
                uid=data.get("mid", 0),
                name=data.get("name", ""),
                face=cls._ensure_https(data.get("face", "")),
                gender=data.get("sex", ""),
            )

    @staticmethod
    def _ensure_https(url: str) -> str:
        """确保URL使用https"""
        if url and not url.startswith("http"):
            return "https:" + url
        return url

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "uid": self.uid,
            "name": self.name,
            "face": self.face,
            "gender": self.gender,
        }
