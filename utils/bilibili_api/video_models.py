"""
B站视频数据模型
提供视频信息等通用数据模型
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class VideoInfo:
    """视频信息"""
    aid: int                    # 视频AV号
    bvid: str                   # 视频BV号
    title: str                  # 视频标题
    description: str            # 视频描述
    cover: str                  # 封面图URL
    duration: int               # 时长（秒）
    pub_date: int               # 发布时间戳
    author_uid: int             # UP主UID
    author_name: str            # UP主名称
    view_count: int = 0         # 播放量
    danmaku_count: int = 0      # 弹幕数
    reply_count: int = 0        # 评论数
    favorite_count: int = 0     # 收藏数
    coin_count: int = 0         # 投币数
    share_count: int = 0        # 分享数
    like_count: int = 0         # 点赞数
    
    @classmethod
    def from_api_data(cls, data: dict) -> 'VideoInfo':
        """从API响应数据创建VideoInfo对象"""
        # 处理封面URL
        cover = data.get('pic', '')
        if cover and not cover.startswith('http'):
            cover = 'https:' + cover
        
        return cls(
            aid=data.get('aid', 0),
            bvid=data.get('bvid', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            cover=cover,
            duration=data.get('duration', 0),
            pub_date=data.get('pubdate', data.get('created', 0)),
            author_uid=data.get('mid', data.get('owner', {}).get('mid', 0)),
            author_name=data.get('author', data.get('owner', {}).get('name', '')),
            view_count=data.get('play', data.get('stat', {}).get('view', 0)),
            danmaku_count=data.get('video_review', data.get('stat', {}).get('danmaku', 0)),
            reply_count=data.get('comment', data.get('stat', {}).get('reply', 0)),
            favorite_count=data.get('favorites', data.get('stat', {}).get('favorite', 0)),
            coin_count=data.get('stat', {}).get('coin', 0),
            share_count=data.get('stat', {}).get('share', 0),
            like_count=data.get('stat', {}).get('like', 0),
        )
    
    def get_video_url(self) -> str:
        """获取视频链接"""
        if self.bvid:
            return f"https://www.bilibili.com/video/{self.bvid}"
        return f"https://www.bilibili.com/video/av{self.aid}"
    
    def format_duration(self) -> str:
        """格式化时长"""
        if self.duration <= 0:
            return "00:00"
        
        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    def format_pub_date(self) -> str:
        """格式化发布时间"""
        if self.pub_date <= 0:
            return "未知"
        pub_time = datetime.fromtimestamp(self.pub_date)
        return pub_time.strftime("%Y-%m-%d %H:%M:%S")
    
    def format_view_count(self) -> str:
        """格式化播放量"""
        if self.view_count >= 10000:
            return f"{self.view_count / 10000:.1f}万"
        return str(self.view_count)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'aid': self.aid,
            'bvid': self.bvid,
            'title': self.title,
            'description': self.description,
            'cover': self.cover,
            'duration': self.duration,
            'pub_date': self.pub_date,
            'author_uid': self.author_uid,
            'author_name': self.author_name,
            'view_count': self.view_count,
            'danmaku_count': self.danmaku_count,
            'reply_count': self.reply_count,
            'favorite_count': self.favorite_count,
            'coin_count': self.coin_count,
            'share_count': self.share_count,
            'like_count': self.like_count,
        }
