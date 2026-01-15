"""
动态数据获取和解析模块
负责直接调用B站API获取动态数据
"""

import aiohttp
import json
import time
from typing import List, Optional
from nonebot.log import logger

from .models import DynamicItem


class DynamicFetcher:
    """B站动态数据获取器"""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        # B站API请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    async def fetch_user_dynamics(self, uid: str) -> Optional[List[DynamicItem]]:
        """直接调用B站API获取用户动态"""
        if not self.session:
            return None

        # B站动态API - Web端空间动态接口
        api_url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"

        try:
            # 构建请求参数
            params = {
                'host_mid': uid,
                'timezone_offset': -480,  # 东八区 (UTC+8)
                'platform': 'web',
                'features': 'itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote',
                'web_location': '333.33',
                'pn': 1,  # 页码
                'ps': 20  # 每页数量
            }

            logger.debug(f"请求B站动态API: {api_url} 用户: {uid}")

            async with self.session.get(
                api_url,
                params=params,
                headers=self.headers,
                timeout=30
            ) as response:

                if response.status != 200:
                    logger.warning(f"B站API请求失败 {uid}: HTTP {response.status}")
                    return None

                response_text = await response.text()
                logger.debug(f"B站API响应长度: {len(response_text)}")

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"解析B站API响应失败 {uid}: {e}")
                    logger.debug(f"原始响应: {response_text[:500]}")
                    return None

                # 检查API响应状态
                if data.get('code') != 0:
                    error_msg = data.get('message', '未知错误')
                    logger.warning(f"B站API返回错误 {uid}: {error_msg}")
                    return None

                items = data.get('data', {}).get('items', [])
                if not items:
                    logger.debug(f"用户 {uid} 没有动态数据")
                    return []

                dynamics = []
                for item in items:
                    try:
                        dynamic_item = self._parse_dynamic_item(item, uid)
                        if dynamic_item:
                            dynamics.append(dynamic_item)
                    except Exception as e:
                        logger.warning(f"解析动态项失败 {uid}: {e}")
                        continue

                # 按时间倒序排列（最新的在前面）
                dynamics.sort(key=lambda x: x.timestamp, reverse=True)
                logger.info(f"成功获取用户 {uid} 的 {len(dynamics)} 条动态")
                return dynamics

        except asyncio.TimeoutError:
            logger.warning(f"B站API请求超时 {uid}")
            return None
        except Exception as e:
            logger.error(f"B站API请求异常 {uid}: {e}")
            return None

    def _parse_dynamic_item(self, item: dict, uid: str) -> Optional[DynamicItem]:
        """解析单个动态项"""
        try:
            # 提取基本信息
            dynamic_id = item.get('id_str')
            if not dynamic_id:
                logger.warning(f"动态缺少ID: {item}")
                return None

            dynamic_id = int(dynamic_id)

            # 提取作者信息
            modules = item.get('modules', {})
            author_module = modules.get('module_author', {})
            author_info = author_module.get('author', {})

            name = author_info.get('name', '未知用户')
            author_uid = author_info.get('mid', uid)

            # 提取时间戳
            timestamp = item.get('pub_ts', int(time.time()))

            # 提取动态类型和内容
            dynamic_type = item.get('type', 0)
            content = self._extract_content_from_item(item)

            # 提取图片
            images = self._extract_images_from_item(item)

            return DynamicItem(
                dynamic_id=dynamic_id,
                uid=int(author_uid),
                name=name,
                timestamp=timestamp,
                dynamic_type=dynamic_type,
                content=content,
                images=images
            )

        except Exception as e:
            logger.warning(f"解析动态项异常: {e}")
            return None

    def _extract_content_from_item(self, item: dict) -> str:
        """从动态项中提取文本内容"""
        try:
            modules = item.get('modules', {})
            dynamic_module = modules.get('module_dynamic', {})

            # 尝试从desc字段提取
            desc = dynamic_module.get('desc', {})
            if desc and desc.get('text'):
                return desc['text']

            # 尝试从major字段提取（图文动态）
            major = dynamic_module.get('major', {})
            if major and major.get('opus', {}):
                opus = major['opus']
                summary = opus.get('summary', {})
                if summary and summary.get('text'):
                    return summary['text']

            return ""

        except Exception as e:
            logger.debug(f"提取动态内容失败: {e}")
            return ""

    def _extract_images_from_item(self, item: dict) -> List[str]:
        """从动态项中提取图片链接"""
        images = []
        try:
            modules = item.get('modules', {})
            dynamic_module = modules.get('module_dynamic', {})
            major = dynamic_module.get('major', {})

            # 提取图文动态的图片
            if major.get('type') == 'MAJOR_TYPE_OPUS':
                opus = major.get('opus', {})
                pics = opus.get('pics', [])
                for pic in pics:
                    if pic.get('url'):
                        images.append(pic['url'])

            # 提取普通动态的图片
            elif major.get('type') == 'MAJOR_TYPE_DRAW':
                draw = major.get('draw', {})
                items = draw.get('items', [])
                for pic_item in items:
                    if pic_item.get('src'):
                        images.append(pic_item['src'])

        except Exception as e:
            logger.debug(f"提取动态图片失败: {e}")

        return images
