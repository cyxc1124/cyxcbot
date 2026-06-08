"""
B站视频API调用模块
提供UP主视频列表获取等API封装
"""

import aiohttp
import json
import math
import random
from typing import List, Optional
from nonebot.log import logger

from .video_models import VideoInfo
from . import wbi


# API 基础配置
BASE_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Origin': 'https://space.bilibili.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


class VideoApi:
    """B站视频API封装"""
    
    def __init__(self, session: aiohttp.ClientSession, cookie: Optional[str] = None):
        self.session = session
        self.cookie = cookie
    
    def _get_headers(self, uid: int) -> dict:
        """获取请求头"""
        headers = {
            **BASE_HEADERS,
            'Referer': f'https://space.bilibili.com/{uid}/video',
        }
        if self.cookie:
            headers['Cookie'] = self.cookie
        return headers
    
    def _generate_dm_img_list(self) -> str:
        """生成dm图像列表，参考RSSHub实现"""
        def generate_gaussian_integer(mean: float, std: float) -> int:
            u1 = random.random()
            u2 = random.random()
            z0 = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
            return max(int(round(z0 * std + mean)), 0)
        
        x = generate_gaussian_integer(1245, 5)
        y = generate_gaussian_integer(1285, 5)
        final_x = 3 * x + 2 * y
        final_y = 4 * x - 5 * y
        timestamp = generate_gaussian_integer(30, 5)
        
        dm_img_data = [{
            "x": final_x,
            "y": final_y,
            "z": 0,
            "timestamp": timestamp,
            "type": 0
        }]
        return json.dumps(dm_img_data)
    
    def _generate_dm_verify_string(self) -> str:
        """生成dm验证字符串"""
        import base64
        return base64.b64encode(b'no webgl').decode()[:-2]
    
    async def get_user_videos(
        self,
        uid: int,
        page: int = 1,
        page_size: int = 30,
        order: str = "pubdate"
    ) -> Optional[List[VideoInfo]]:
        """
        获取UP主投稿视频列表
        
        Args:
            uid: UP主UID
            page: 页码
            page_size: 每页数量（最大50）
            order: 排序方式 pubdate-最新发布 click-最多播放 stow-最多收藏
        
        Returns:
            视频列表
        """
        api_url = "https://api.bilibili.com/x/space/wbi/arc/search"
        
        try:
            # 构建基础参数
            params = {
                'mid': str(uid),
                'pn': str(page),
                'ps': str(min(page_size, 50)),
                'tid': '0',
                'special_type': '',
                'order': order,
                'index': '0',
                'keyword': '',
                'order_avoided': 'true',
                'platform': 'web',
                'web_location': '333.1387',
                'dm_img_list': self._generate_dm_img_list(),
                'dm_img_str': self._generate_dm_verify_string(),
                'dm_cover_img_str': self._generate_dm_verify_string(),
                'dm_img_inter': json.dumps({
                    "ds": [],
                    "wh": [0, 0, 0],
                    "of": [0, 0, 0]
                }),
            }
            
            # 使用 WBI 签名
            signed_query = await wbi.sign_params(self.session, params, self.cookie)
            
            if signed_query:
                url = f"{api_url}?{signed_query}"
            else:
                logger.warning("无法获取WBI签名，尝试无签名请求")
                from urllib.parse import urlencode
                url = f"{api_url}?{urlencode(params)}"
            
            headers = self._get_headers(uid)
            
            logger.debug(f"请求UP主 {uid} 视频列表: {url[:100]}...")
            
            async with self.session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    logger.warning(f"获取UP主 {uid} 视频列表失败: HTTP {response.status}")
                    return None
                
                data = await response.json()
                
                if data.get('code') != 0:
                    logger.warning(f"获取UP主 {uid} 视频列表失败: {data.get('message', '未知错误')}")
                    return None
                
                vlist = data.get('data', {}).get('list', {}).get('vlist', [])
                
                if not vlist:
                    logger.debug(f"UP主 {uid} 没有投稿视频")
                    return []
                
                videos = []
                for item in vlist:
                    try:
                        video = VideoInfo.from_api_data(item)
                        videos.append(video)
                    except Exception as e:
                        logger.warning(f"解析视频信息失败: {e}")
                        continue
                
                logger.info(f"成功获取UP主 {uid} 的 {len(videos)} 个视频")
                return videos
                
        except Exception as e:
            logger.error(f"获取UP主 {uid} 视频列表异常: {e}")
            return None
    
    async def get_latest_video(self, uid: int) -> Optional[VideoInfo]:
        """
        获取UP主最新投稿视频
        
        Args:
            uid: UP主UID
        
        Returns:
            最新视频信息
        """
        videos = await self.get_user_videos(uid, page=1, page_size=1, order="pubdate")
        if videos and len(videos) > 0:
            return videos[0]
        return None

    async def get_video_detail(
        self,
        *,
        bvid: Optional[str] = None,
        aid: Optional[int] = None,
    ) -> Optional[VideoInfo]:
        """获取单个视频详情（BV 或 AV）。"""
        if not bvid and not aid:
            return None

        api_url = "https://api.bilibili.com/x/web-interface/view"
        params: dict[str, str | int] = {}
        if bvid:
            params["bvid"] = bvid
        else:
            params["aid"] = aid

        headers = {
            **BASE_HEADERS,
            "Referer": "https://www.bilibili.com/",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        try:
            async with self.session.get(
                api_url,
                params=params,
                headers=headers,
                timeout=15,
            ) as response:
                if response.status != 200:
                    logger.warning(f"获取视频详情失败: HTTP {response.status}")
                    return None

                payload = await response.json()
                if payload.get("code") != 0:
                    logger.warning(f"获取视频详情失败: {payload.get('message', '未知错误')}")
                    return None

                data = payload.get("data") or {}
                return VideoInfo.from_api_data(data)
        except Exception as exc:
            logger.error(f"获取视频详情异常: {exc}")
            return None


class VideoApiManager:
    """视频API管理器（单例模式）"""
    
    _instance: Optional['VideoApiManager'] = None
    _session: Optional[aiohttp.ClientSession] = None
    _api: Optional[VideoApi] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def init(self, cookie: Optional[str] = None):
        """初始化API管理器"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        if self._api is None:
            self._api = VideoApi(self._session, cookie)
        else:
            self._api.cookie = cookie
        logger.info("视频API管理器已初始化")
    
    async def close(self):
        """关闭API管理器"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self._api = None
        logger.info("视频API管理器已关闭")
    
    @property
    def api(self) -> VideoApi:
        """获取API实例"""
        if self._api is None:
            raise RuntimeError("VideoApiManager 未初始化，请先调用 init()")
        return self._api
    
    async def get_user_videos(self, uid: int, **kwargs) -> Optional[List[VideoInfo]]:
        """获取UP主视频列表"""
        return await self.api.get_user_videos(uid, **kwargs)
    
    async def get_latest_video(self, uid: int) -> Optional[VideoInfo]:
        """获取UP主最新视频"""
        return await self.api.get_latest_video(uid)

    async def get_video_detail(
        self,
        *,
        bvid: Optional[str] = None,
        aid: Optional[int] = None,
    ) -> Optional[VideoInfo]:
        """获取单个视频详情"""
        return await self.api.get_video_detail(bvid=bvid, aid=aid)


# 全局API管理器实例
video_api_manager = VideoApiManager()
