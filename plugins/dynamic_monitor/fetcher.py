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
        # B站API请求头 - 参考RSSHub实现
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Referer': f'https://space.bilibili.com/{uid}/',  # 动态设置Referer
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    async def fetch_user_dynamics(self, uid: str, current_pinned_id: Optional[int] = None, cookie: Optional[str] = None) -> Optional[tuple[List[DynamicItem], Optional[int]]]:
        """直接调用B站API获取用户动态

        Args:
            uid: 用户ID
            current_pinned_id: 当前记录的置顶动态ID
            cookie: B站用户Cookie（可选，用于绕过限制）

        Returns:
            (动态列表, 当前置顶动态ID)
        """
        if not self.session:
            return None

        # B站动态API - Web端空间动态接口
        api_url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"

        try:
            # 构建请求参数 - 参考RSSHub实现
            # 基础参数 - 与RSSHub完全一致
            base_params = f"offset=&host_mid={uid}&platform=web&features=itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote"

            # 添加dm验证信息 (模拟RSSHub的addDmVerifyInfo)
            dm_img_str = self._generate_dm_verify_string()
            dm_cover_img_str = self._generate_dm_verify_string()
            dm_img_list = self._generate_dm_img_list()  # 动态生成dm图像列表

            params_str = f"{base_params}&dm_img_list={dm_img_list}&dm_img_str={dm_img_str}&dm_cover_img_str={dm_cover_img_str}"

            # 解析为字典格式供aiohttp使用
            params = {}
            for param in params_str.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value

            logger.debug(f"请求B站动态API: {api_url} 用户: {uid}")

            # 动态设置请求头
            request_headers = self.headers.copy()
            request_headers['Referer'] = f'https://space.bilibili.com/{uid}/'

            # 添加Cookie（如果提供）
            if cookie:
                request_headers['Cookie'] = cookie
                logger.debug(f"使用Cookie进行B站API请求: cookie={cookie}")

            async with self.session.get(
                api_url,
                params=params,
                headers=request_headers,
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
                    return [], None

                dynamics = []
                current_pinned_id = None

                for item in items:
                    try:
                        # 检测置顶动态
                        modules = item.get('modules', {})
                        module_tag = modules.get('module_tag')
                        is_pinned = (module_tag and isinstance(module_tag, dict)
                                   and module_tag.get('text') == '置顶')

                        if is_pinned:
                            pinned_id = item.get('id_str')
                            if pinned_id:
                                pinned_id_int = int(pinned_id)
                                current_pinned_id = pinned_id_int
                            # 置顶动态总是包含在结果中，由调用方决定是否推送
                            should_include = True
                            if should_include:
                                logger.info(f"检测到新的置顶动态: {pinned_id}")
                        else:
                            # 非置顶动态直接包含
                            should_include = True

                        if should_include:
                            dynamic_item = self._parse_dynamic_item(item, uid, is_pinned)
                            if dynamic_item:
                                dynamics.append(dynamic_item)

                    except Exception as e:
                        logger.warning(f"解析动态项失败 {uid}: {e}")
                        continue

                # 按时间倒序排列（最新的在前面）
                dynamics.sort(key=lambda x: x.timestamp, reverse=True)
                logger.info(f"成功获取用户 {uid} 的 {len(dynamics)} 条动态")
                return dynamics, current_pinned_id

        except asyncio.TimeoutError:
            logger.warning(f"B站API请求超时 {uid}")
            return None
        except Exception as e:
            logger.error(f"B站API请求异常 {uid}: {e}")
            return None

    def _parse_dynamic_item(self, item: dict, uid: str, is_pinned: bool = False) -> Optional[DynamicItem]:
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
            author_type = author_info.get('type', 'AUTHOR_TYPE_UNKNOWN')
            author_type_desc = self._get_author_type_description(author_type)
            author_type = author_info.get('type', 'AUTHOR_TYPE_NORMAL')

            # 提取时间戳
            timestamp = item.get('pub_ts', int(time.time()))

            # 提取动态类型 - 只需基本类型信息用于描述
            bili_dynamic_type = item.get('type', 'DYNAMIC_TYPE_WORD')

            # 过滤直播动态，因为直播推送由其他插件负责
            if bili_dynamic_type in ('DYNAMIC_TYPE_LIVE_RCMD', 'DYNAMIC_TYPE_LIVE'):
                logger.debug(f"跳过直播动态: {dynamic_id}, 类型={bili_dynamic_type}, 作者={name}")
                return None

            dynamic_type = self._map_dynamic_type(bili_dynamic_type)

            # 初始化内容为空，因为我们要截图，不需要解析详细内容
            content = ""

            # 特殊处理转发动态 - 需要解析原始动态信息用于描述
            if bili_dynamic_type == 'DYNAMIC_TYPE_FORWARD':
                orig_info = self._extract_forward_orig_info(item)
                if orig_info:
                    # 设置转发描述
                    content = f"转发了{orig_info['author']}的{orig_info['type_desc']}"

            logger.debug(f"动态 {dynamic_id}: B站类型={bili_dynamic_type}, 映射类型={dynamic_type}, 作者={name}")

            # 图片链接不需要，因为我们要截图
            images = []

            return DynamicItem(
                dynamic_id=dynamic_id,
                uid=int(author_uid),
                name=name,
                timestamp=timestamp,
                dynamic_type=dynamic_type,
                content=content,
                images=images,
                author_type=author_type
            )

        except Exception as e:
            logger.warning(f"解析动态项异常: {e}")
            return None


    def _extract_forward_orig_info(self, item: dict) -> Optional[dict]:
        """提取转发动态的原始信息"""
        try:
            modules = item.get('modules', {})
            dynamic_module = modules.get('module_dynamic', {})
            orig = dynamic_module.get('orig')

            if not orig:
                return None

            # 提取原始动态的作者信息
            orig_modules = orig.get('modules', {})
            orig_author = orig_modules.get('module_author', {})
            orig_author_info = orig_author.get('author', {})
            orig_author_name = orig_author_info.get('name', '未知用户')

            # 提取原始动态的类型
            orig_type = orig.get('type', 'DYNAMIC_TYPE_UNKNOWN')
            orig_type_desc = self._get_forward_type_description(orig_type)

            return {
                'author': orig_author_name,
                'type_desc': orig_type_desc,
                'orig_type': orig_type
            }

        except Exception as e:
            logger.debug(f"解析转发原始信息失败: {e}")
            return None

    def _get_forward_type_description(self, bili_type: str) -> str:
        """获取转发类型描述"""
        type_descriptions = {
            'DYNAMIC_TYPE_WORD': '动态',
            'DYNAMIC_TYPE_DRAW': '图文动态',
            'DYNAMIC_TYPE_FORWARD': '动态',
            'DYNAMIC_TYPE_AV': '视频',
            'DYNAMIC_TYPE_ARTICLE': '专栏',
            'DYNAMIC_TYPE_MUSIC': '音频',
            'DYNAMIC_TYPE_LIVE': '直播',
            'DYNAMIC_TYPE_LIVE_RCMD': '直播',
        }
        return type_descriptions.get(bili_type, '动态')

    def _generate_dm_img_list(self) -> str:
        """生成dm图像列表，参考RSSHub的getDmImgList实现"""
        import random

        # 生成高斯分布的随机坐标 (参考RSSHub的generateGaussianInteger)
        def generate_gaussian_integer(mean: float, std: float) -> int:
            # 使用Box-Muller变换生成高斯分布随机数
            import math
            u1 = random.random()
            u2 = random.random()
            z0 = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
            return max(int(round(z0 * std + mean)), 0)

        # 生成基础坐标
        x = generate_gaussian_integer(1245, 5)
        y = generate_gaussian_integer(1285, 5)

        # 按照RSSHub的算法计算最终坐标
        final_x = 3 * x + 2 * y
        final_y = 4 * x - 5 * y

        # 生成时间戳 (围绕30的随机数)
        timestamp = generate_gaussian_integer(30, 5)

        # 构建dm图像列表 - 与RSSHub完全一致的格式
        dm_img_data = [{
            "x": final_x,
            "y": final_y,
            "z": 0,
            "timestamp": timestamp,
            "type": 0
        }]

        return json.dumps(dm_img_data)

    def _generate_dm_verify_string(self) -> str:
        """生成dm验证字符串，参考RSSHub的实现"""
        import base64
        # 模拟RSSHub: Buffer.from('no webgl').toString('base64').slice(0, -2)
        return base64.b64encode(b'no webgl').decode()[:-2]

    def _map_dynamic_type(self, bili_type: str) -> int:
        """将B站动态类型映射为内部类型编号

        B站动态类型映射：
        - DYNAMIC_TYPE_WORD: 纯文字动态
        - DYNAMIC_TYPE_DRAW: 图文动态
        - DYNAMIC_TYPE_FORWARD: 转发动态
        - DYNAMIC_TYPE_AV: 投稿视频动态
        - DYNAMIC_TYPE_ARTICLE: 投稿专栏动态
        - DYNAMIC_TYPE_MUSIC: 投稿音频动态
        """
        type_mapping = {
            'DYNAMIC_TYPE_WORD': 4,      # 文字动态
            'DYNAMIC_TYPE_DRAW': 2,      # 图文动态
            'DYNAMIC_TYPE_FORWARD': 1,   # 转发动态
            'DYNAMIC_TYPE_AV': 8,        # 投稿视频
            'DYNAMIC_TYPE_ARTICLE': 64,  # 投稿专栏
            'DYNAMIC_TYPE_MUSIC': 256,   # 投稿音频
            'DYNAMIC_TYPE_LIVE': 16,     # 直播动态
            'DYNAMIC_TYPE_LIVE_RCMD': 16, # 直播推荐
        }

        return type_mapping.get(bili_type, 0)  # 默认其他动态

    def _get_author_type_description(self, author_type: str) -> str:
        """获取作者类型描述"""
        type_descriptions = {
            'AUTHOR_TYPE_NORMAL': '普通用户',
            'AUTHOR_TYPE_OFFICIAL': '官方账号',
            'AUTHOR_TYPE_BIZ': '商业账号',
            'AUTHOR_TYPE_BIG_VIP': '大会员',
        }
        return type_descriptions.get(author_type, '未知类型')
