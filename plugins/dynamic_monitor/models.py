"""
动态数据模型
定义动态相关的核心数据结构
"""

from typing import List
from datetime import datetime, timezone, timedelta


class DynamicItem:
    """动态项数据类"""

    def __init__(self, dynamic_id: int, uid: int, name: str, timestamp: int,
                 dynamic_type: int, title: str = "", content: str = "",
                 images: List[str] = None, author_type: str = ""):
        self.id = dynamic_id
        self.uid = uid
        self.name = name
        self.timestamp = timestamp
        self.type = dynamic_type
        self.title = title
        self.content = content
        self.images = images or []
        self.author_type = author_type  # 作者类型
        self.url = f"https://t.bilibili.com/{dynamic_id}"


    def get_beijing_time(self) -> str:
        """获取北京时间格式化的字符串"""
        # 时间戳已经是北京时间，直接转换
        beijing_time = datetime.fromtimestamp(self.timestamp)
        # 格式化为易读的字符串
        return beijing_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_type_description(self) -> str:
        """获取动态类型描述"""
        # 如果是转发动态且内容已经包含转发信息，直接使用内容
        if self.type == 1 and self.content and self.content.startswith('转发了'):
            return self.content

        type_msg = {
            0: "发布了新动态",
            1: "转发了动态",
            2: "发布了新图文动态",
            4: "发布了新文字动态",
            8: "发布了新投稿视频",
            16: "发布了直播",
            32: "发布了新音频",
            64: "发布了新专栏",
            256: "发布了新音频",
            512: "发布了新番剧",
            1024: "发布了新影视",
            2048: "发布了新剧集"
        }
        return type_msg.get(self.type, "发布了新动态")