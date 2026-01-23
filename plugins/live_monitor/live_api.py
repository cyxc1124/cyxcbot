"""
B站直播API调用模块
参考 blrec 的 API 实现
"""

import aiohttp
import asyncio
import json
import re
from typing import Optional, Tuple
from nonebot.log import logger

from .models import RoomInfo, UserInfo, LiveStatus


# API 基础配置
BASE_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Origin': 'https://live.bilibili.com',
}

# 正则表达式用于从HTML页面提取直播状态（备用方案）
_LIVE_STATUS_PATTERN = re.compile(rb'"live_status"\s*:\s*(\d)')
_INFO_PATTERN = re.compile(
    rb'<script>\s*window\.__NEPTUNE_IS_MY_WAIFU__\s*=\s*(\{.*?\})\s*</script>'
)


class LiveApi:
    """B站直播API封装"""
    
    def __init__(self, session: aiohttp.ClientSession, cookie: Optional[str] = None):
        self.session = session
        self.cookie = cookie
        self._user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    def _get_headers(self, room_id: int) -> dict:
        """获取请求头"""
        headers = {
            **BASE_HEADERS,
            'Referer': f'https://live.bilibili.com/{room_id}',
            'User-Agent': self._user_agent,
        }
        if self.cookie:
            headers['Cookie'] = self.cookie
        return headers
    
    async def get_room_info(self, room_id: int) -> Optional[RoomInfo]:
        """
        获取直播间信息
        优先使用API，失败时使用HTML页面解析
        """
        try:
            # 优先尝试 API
            room_info_data = await self._get_room_info_via_api(room_id)
            return RoomInfo.from_api_data(room_info_data)
        except Exception as e:
            logger.warning(f"API获取房间 {room_id} 信息失败: {e}，尝试HTML解析")
            try:
                # 备用方案：从HTML页面解析
                room_info_data = await self._get_room_info_via_html(room_id)
                return RoomInfo.from_api_data(room_info_data)
            except Exception as e2:
                logger.error(f"HTML解析房间 {room_id} 信息也失败: {e2}")
                return None
    
    async def get_user_info(self, room_id: int, uid: Optional[int] = None) -> Optional[UserInfo]:
        """获取主播用户信息"""
        try:
            data = await self._get_info_by_room(room_id)
            return UserInfo.from_api_data(data)
        except Exception as e:
            logger.warning(f"获取房间 {room_id} 主播信息失败: {e}")
            return None
    
    async def get_live_status(self, room_id: int) -> Optional[LiveStatus]:
        """
        获取直播状态
        优先使用API，失败时使用HTML页面解析
        """
        try:
            room_info_data = await self._get_room_info_via_api(room_id)
            return LiveStatus(int(room_info_data['live_status']))
        except Exception as e:
            logger.debug(f"API获取房间 {room_id} 状态失败: {e}，尝试HTML解析")
            try:
                status = await self._get_live_status_via_html(room_id)
                return LiveStatus(status)
            except Exception as e2:
                logger.error(f"获取房间 {room_id} 直播状态失败: {e2}")
                return None
    
    async def get_room_and_user_info(self, room_id: int) -> Tuple[Optional[RoomInfo], Optional[UserInfo]]:
        """同时获取房间信息和用户信息"""
        try:
            data = await self._get_info_by_room(room_id)
            room_info = RoomInfo.from_api_data(data['room_info'])
            user_info = UserInfo.from_api_data(data)
            return room_info, user_info
        except Exception as e:
            logger.warning(f"获取房间 {room_id} 完整信息失败: {e}")
            # 尝试单独获取
            room_info = await self.get_room_info(room_id)
            user_info = await self.get_user_info(room_id) if room_info else None
            return room_info, user_info
    
    async def _get_info_by_room(self, room_id: int) -> dict:
        """调用 getInfoByRoom 接口获取房间完整信息"""
        # Web API
        url = f"https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom"
        params = {'room_id': room_id}
        headers = self._get_headers(room_id)
        
        async with self.session.get(url, params=params, headers=headers, timeout=10) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
            
            data = await response.json()
            if data.get('code') != 0:
                raise Exception(f"API错误: {data.get('message', '未知错误')}")
            
            return data['data']
    
    async def _get_room_info_via_api(self, room_id: int) -> dict:
        """通过API获取房间信息"""
        try:
            # 优先使用 getInfoByRoom
            data = await self._get_info_by_room(room_id)
            return data['room_info']
        except Exception:
            # 备用：使用 get_info
            url = f"https://api.live.bilibili.com/room/v1/Room/get_info"
            params = {'room_id': room_id}
            headers = self._get_headers(room_id)
            
            async with self.session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                data = await response.json()
                if data.get('code') != 0:
                    raise Exception(f"API错误: {data.get('message', '未知错误')}")
                
                return data['data']
    
    async def _get_room_info_via_html(self, room_id: int) -> dict:
        """通过HTML页面解析获取房间信息（备用方案）"""
        url = f'https://live.bilibili.com/{room_id}'
        headers = self._get_headers(room_id)
        
        async with self.session.get(url, headers=headers, timeout=15) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
            
            html_data = await response.read()
        
        # 尝试从 __NEPTUNE_IS_MY_WAIFU__ 提取数据
        match = _INFO_PATTERN.search(html_data)
        if not match:
            raise Exception("无法从HTML页面提取数据")
        
        string = match.group(1).decode(encoding='utf8')
        info = json.loads(string)
        
        if info.get('roomInfoRes', {}).get('code') != 0:
            raise Exception(f"roomInfoRes 无效: {info.get('roomInfoRes')}")
        
        return info['roomInfoRes']['data']['room_info']
    
    async def _get_live_status_via_html(self, room_id: int) -> int:
        """通过HTML页面正则匹配获取直播状态（最简备用方案）"""
        url = f'https://live.bilibili.com/{room_id}'
        headers = self._get_headers(room_id)
        
        async with self.session.get(url, headers=headers, timeout=15) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
            
            html_data = await response.read()
        
        match = _LIVE_STATUS_PATTERN.search(html_data)
        if not match:
            raise Exception("无法从HTML页面提取直播状态")
        
        return int(match.group(1))


class LiveApiManager:
    """直播API管理器（单例模式）"""
    
    _instance: Optional['LiveApiManager'] = None
    _session: Optional[aiohttp.ClientSession] = None
    _api: Optional[LiveApi] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def init(self, cookie: Optional[str] = None):
        """初始化API管理器"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        self._api = LiveApi(self._session, cookie)
        logger.info("直播API管理器已初始化")
    
    async def close(self):
        """关闭API管理器"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self._api = None
        logger.info("直播API管理器已关闭")
    
    @property
    def api(self) -> LiveApi:
        """获取API实例"""
        if self._api is None:
            raise RuntimeError("LiveApiManager 未初始化，请先调用 init()")
        return self._api
    
    async def get_room_info(self, room_id: int) -> Optional[RoomInfo]:
        """获取房间信息"""
        return await self.api.get_room_info(room_id)
    
    async def get_user_info(self, room_id: int) -> Optional[UserInfo]:
        """获取用户信息"""
        return await self.api.get_user_info(room_id)
    
    async def get_live_status(self, room_id: int) -> Optional[LiveStatus]:
        """获取直播状态"""
        return await self.api.get_live_status(room_id)
    
    async def get_room_and_user_info(self, room_id: int) -> Tuple[Optional[RoomInfo], Optional[UserInfo]]:
        """同时获取房间和用户信息"""
        return await self.api.get_room_and_user_info(room_id)


# 全局API管理器实例
api_manager = LiveApiManager()
