"""
动态数据获取和解析模块
负责从RSSHub获取和解析动态数据
"""

import aiohttp
import feedparser
import time
from typing import List, Optional
from urllib.parse import urlparse, parse_qs
from nonebot.log import logger

from .models import DynamicItem


class DynamicFetcher:
    """动态数据获取器"""

    def __init__(self, session: aiohttp.ClientSession, rsshub_base_url: str = "https://rsshub.app"):
        self.session = session
        self.rsshub_base_url = rsshub_base_url

    async def fetch_user_dynamics(self, uid: str) -> Optional[List[DynamicItem]]:
        """从RSSHub获取用户动态feed"""
        rsshub_url = f"{self.rsshub_base_url}/bilibili/user/dynamic/{uid}"

        try:
            async with self.session.get(rsshub_url, timeout=30) as response:
                if response.status != 200:
                    logger.error(f"获取RSS失败 {uid}: HTTP {response.status}")
                    return None

                feed_content = await response.text()
                feed = feedparser.parse(feed_content)

                if feed.bozo:  # 解析错误
                    logger.error(f"RSS解析错误 {uid}: {feed.bozo_exception}")
                    return None

                dynamics = []
                for entry in feed.entries:
                    # 从链接中提取动态ID
                    dynamic_id = self._extract_dynamic_id_from_url(entry.link)
                    if not dynamic_id:
                        continue

                    # 获取UP主名称 - 直接使用author字段
                    if hasattr(entry, 'author') and entry.author:
                        name = entry.author.strip()
                    else:
                        logger.error(f"RSS条目缺少author字段，跳过此条目: {entry.title}")
                        continue  # 跳过这条动态

                    # 从published_parsed获取时间戳
                    timestamp = int(time.mktime(entry.published_parsed)) if hasattr(entry, 'published_parsed') else int(time.time())

                    # 解析动态类型和内容
                    dynamic_type = self._parse_dynamic_type(entry.title)
                    content = self._clean_html_content(entry.summary if hasattr(entry, 'summary') else "")

                    # 提取图片链接
                    images = self._extract_images_from_content(content)

                    dynamic = DynamicItem(
                        dynamic_id=dynamic_id,
                        uid=int(uid),
                        name=name,
                        timestamp=timestamp,
                        dynamic_type=dynamic_type,
                        content=content,
                        images=images
                    )
                    dynamics.append(dynamic)

                # 按时间倒序排列（最新的在前面）
                dynamics.sort(key=lambda x: x.timestamp, reverse=True)
                return dynamics

        except asyncio.TimeoutError:
            logger.warning(f"获取RSS超时 {uid}")
            return None
        except Exception as e:
            logger.error(f"获取RSS异常 {uid}: {e}")
            return None

    def _extract_dynamic_id_from_url(self, url: str) -> Optional[int]:
        """从动态链接中提取动态ID"""
        try:
            parsed = urlparse(url)
            if 't.bilibili.com' in parsed.netloc:
                path_parts = parsed.path.strip('/').split('/')
                if path_parts:
                    return int(path_parts[0])
            # 尝试从查询参数中提取
            query_params = parse_qs(parsed.query)
            if 'id' in query_params:
                return int(query_params['id'][0])
        except (ValueError, IndexError):
            pass
        return None


    def _parse_dynamic_type(self, title: str) -> int:
        """根据标题解析动态类型"""
        title_lower = title.lower()
        if "转发" in title or "repost" in title_lower:
            return 1  # 转发
        elif "视频" in title or "video" in title_lower:
            return 8  # 投稿
        elif "专栏" in title or "article" in title_lower:
            return 64  # 专栏
        elif "音频" in title or "music" in title_lower:
            return 256  # 音频
        elif "图文" in title or "draw" in title_lower:
            return 2  # 图文
        elif "文字" in title or "word" in title_lower:
            return 4  # 文字
        else:
            return 0  # 其他动态

    def _clean_html_content(self, content: str) -> str:
        """清理HTML内容"""
        import re
        # 移除HTML标签
        clean = re.compile('<.*?>')
        content = re.sub(clean, '', content)
        # 移除多余空白
        content = ' '.join(content.split())
        return content

    def _extract_images_from_content(self, content: str) -> List[str]:
        """从内容中提取图片链接"""
        import re
        # 匹配img标签的src属性
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        matches = re.findall(img_pattern, content, re.IGNORECASE)
        return matches