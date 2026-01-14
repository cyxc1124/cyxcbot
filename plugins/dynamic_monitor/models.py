"""
动态数据模型
定义动态相关的核心数据结构
"""

from typing import List
from datetime import datetime


class DynamicItem:
    """动态项数据类"""

    def __init__(self, dynamic_id: int, uid: int, name: str, timestamp: int,
                 dynamic_type: int, title: str = "", content: str = "",
                 images: List[str] = None):
        self.id = dynamic_id
        self.uid = uid
        self.name = name
        self.timestamp = timestamp
        self.type = dynamic_type
        self.title = title
        self.content = content
        self.images = images or []
        self.url = f"https://t.bilibili.com/{dynamic_id}"

    @property
    def datetime(self) -> datetime:
        """获取动态发布时间"""
        return datetime.fromtimestamp(self.timestamp)

    def get_type_description(self) -> str:
        """获取动态类型描述"""
        type_msg = {
            0: "发布了新动态",
            1: "转发了一条动态",
            2: "发布了新图文动态",
            4: "发布了新文字动态",
            8: "发布了新投稿",
            16: "发布了短视频",
            32: "发布了新音频",
            64: "发布了新专栏",
            256: "发布了新音频",
            512: "发布了新番剧",
            1024: "发布了新影视",
            2048: "发布了新剧集"
        }
        return type_msg.get(self.type, "发布了新动态")