"""
动态数据获取和解析模块
负责直接调用B站API获取动态数据
"""

import aiohttp
import json
import time
from typing import List, Optional
from urllib.parse import urlencode
from nonebot.log import logger

from .models import DynamicItem


class DynamicFetcher:
    """B站动态数据获取器"""

    def __init__(self, session: aiohttp.ClientSession, cookie: Optional[str] = None):
        self.session = session
        self.cookie = cookie  # 保存cookie供后续使用
        # B站API请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Referer': f'https://space.bilibili.com/',
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

            # 构建完整的请求URL用于日志
            full_url = f"{api_url}?{urlencode(params)}"
            logger.debug(f"请求B站动态API: {full_url}")

            # 动态设置请求头
            request_headers = self.headers.copy()

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
                            dynamic_item = await self._parse_dynamic_item(item, uid, is_pinned)
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

    async def _parse_dynamic_item(self, item: dict, uid: str, is_pinned: bool = False) -> Optional[DynamicItem]:
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

            author_uid = author_info.get('mid', uid)

            # 暂时不获取用户名，只保存UID，在需要推送时再获取
            name = f"UP主_{author_uid}"  # 临时占位符，推送时会被替换

            author_type = author_info.get('type', 'AUTHOR_TYPE_UNKNOWN')
            author_type_desc = self._get_author_type_description(author_type)
            author_type = author_info.get('type', 'AUTHOR_TYPE_NORMAL')

            # 提取时间戳
            timestamp = item.get('pub_ts', int(time.time()))

            # 提取动态类型 - 只需基本类型信息用于描述
            bili_dynamic_type = item.get('type', 'DYNAMIC_TYPE_WORD')

            # 过滤直播动态，因为直播推送由其他插件负责
            if bili_dynamic_type in ('DYNAMIC_TYPE_LIVE_RCMD', 'DYNAMIC_TYPE_LIVE'):
                logger.debug(f"跳过直播动态: {dynamic_id}, 类型={bili_dynamic_type}, UID={author_uid}")
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

            logger.debug(f"动态 {dynamic_id}: B站类型={bili_dynamic_type}, 映射类型={dynamic_type}, UID={author_uid}")

            # 图片链接不需要，因为我们要截图
            images = []

            # 创建DynamicItem对象
            dynamic_item = DynamicItem(
                dynamic_id=dynamic_id,
                uid=int(author_uid),
                name=name,
                timestamp=timestamp,
                dynamic_type=dynamic_type,
                content=content,
                images=images,
                author_type=author_type
            )

            # 对于视频动态，尝试提取视频链接而不是动态链接
            if bili_dynamic_type == 'DYNAMIC_TYPE_AV':
                try:
                    dynamic_module = modules.get('module_dynamic', {})
                    major = dynamic_module.get('major', {})

                    # 尝试从archive信息中提取视频链接
                    if major and isinstance(major, dict):
                        archive = major.get('archive')
                        if archive and isinstance(archive, dict):
                            # 优先使用bvid构造链接，如果没有则使用aid
                            bvid = archive.get('bvid')
                            if bvid:
                                dynamic_item.url = f"https://www.bilibili.com/video/{bvid}"
                                logger.debug(f"视频动态 {dynamic_id} 使用BV号视频链接: {dynamic_item.url}")
                            else:
                                aid = archive.get('aid')
                                if aid:
                                    dynamic_item.url = f"https://www.bilibili.com/video/av{aid}"
                                    logger.debug(f"视频动态 {dynamic_id} 使用AV号视频链接: {dynamic_item.url}")
                except Exception as e:
                    logger.debug(f"提取视频链接失败，使用默认动态链接: {e}")
                    # 失败时保持默认的动态链接

            return dynamic_item

        except Exception as e:
            logger.warning(f"解析动态项异常: {e}")
            return None

    async def _get_user_name_from_api(self, uid: str) -> Optional[str]:
        """从B站API获取用户信息"""
        try:
            # 按照RSSHub的方式使用WBI签名API
            user_info_url = "https://api.bilibili.com/x/space/wbi/acc/info"

            # 基础参数字符串（按照RSSHub格式）
            base_params = f"mid={uid}&token=&platform=web&web_location=1550101"

            # 生成WBI签名参数
            signed_params = await self._add_wbi_verify_info(base_params)

            # 请求头
            user_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': f'https://space.bilibili.com/{uid}/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
            }

            # 如果有Cookie，添加到请求头
            if self.cookie:
                user_headers['Cookie'] = self.cookie

            logger.debug(f"获取UP主 {uid} 信息，请求URL: {user_info_url}?{signed_params}")

            async with self.session.get(
                user_info_url,
                params=signed_params,
                headers=user_headers,
                timeout=10
            ) as response:

                if response.status != 200:
                    logger.debug(f"获取用户信息失败 {uid}: HTTP {response.status}")
                    return None

                data = await response.json()
                logger.debug(f"用户信息API响应 {uid}: code={data.get('code')}")

                if data.get('code') != 0:
                    logger.debug(f"获取用户信息失败 {uid}: {data.get('message', '未知错误')}")
                    return None

                user_data = data.get('data', {})
                name = user_data.get('name')
                if name:
                    logger.debug(f"成功获取UP主 {uid} 信息: {name}")
                    return name
                else:
                    logger.debug(f"用户信息中没有找到名字 {uid}")
                    return None

        except Exception as e:
            logger.debug(f"获取UP主信息异常 {uid}: {e}")
            return None

    async def _add_wbi_verify_info(self, params: str) -> str:
        """添加WBI签名参数（按照RSSHub的实现）"""
        try:
            import hashlib
            import time
            import json
            from urllib.parse import urlencode

            # 获取WBI验证字符串
            wbi_verify_string = await self._get_wbi_verify_string()
            if not wbi_verify_string:
                logger.debug("无法获取WBI验证字符串，回退到无签名模式")
                return params

            # 解析参数并排序
            param_dict = {}
            for param in params.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    param_dict[key] = value

            # 按key排序
            sorted_params = '&'.join([f"{k}={param_dict[k]}" for k in sorted(param_dict.keys())])

            # 添加时间戳
            wts = int(time.time())

            # 生成w_rid签名
            sign_str = f"{sorted_params}&wts={wts}{wbi_verify_string}"
            w_rid = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

            # 添加签名参数
            param_dict['w_rid'] = w_rid
            param_dict['wts'] = str(wts)

            # 构建最终参数字符串
            final_params = '&'.join([f"{k}={v}" for k, v in param_dict.items()])
            return final_params

        except Exception as e:
            logger.debug(f"WBI签名生成失败: {e}")
            # 如果签名失败，返回原始参数
            return params

    async def _get_wbi_verify_string(self) -> Optional[str]:
        """获取WBI验证字符串（按照RSSHub的实现）"""
        try:
            # 获取导航信息
            nav_url = "https://api.bilibili.com/x/web-interface/nav"
            nav_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
            }

            if self.cookie:
                nav_headers['Cookie'] = self.cookie

            async with self.session.get(nav_url, headers=nav_headers, timeout=10) as response:
                if response.status != 200:
                    logger.debug("导航API请求失败")
                    return None

                nav_data = await response.json()
                if nav_data.get('code') != 0 or 'wbi_img' not in nav_data.get('data', {}):
                    logger.debug("导航数据获取失败")
                    return None

                nav_data = nav_data['data']

            # 提取img_key和sub_key
            img_url = nav_data['wbi_img']['img_url']
            sub_url = nav_data['wbi_img']['sub_url']

            # 按照RSSHub的方式提取key
            img_key = img_url.split('/')[-1].split('.')[0]
            sub_key = sub_url.split('/')[-1].split('.')[0]
            r = img_key + sub_key

            # 获取混淆数组（硬编码RSSHub中的数组）
            # 这是一个固定的混淆数组，从B站的JS文件中提取
            mixin_key = [
                46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
                33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
                26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36,
                20, 34, 44, 52
            ]

            # 重新排列字符
            result = []
            for t in mixin_key:
                if t < len(r):
                    result.append(r[t])

            # 取前32个字符
            wbi_verify_string = ''.join(result)[:32]
            logger.debug(f"生成WBI验证字符串成功: {wbi_verify_string[:8]}...")
            return wbi_verify_string

        except Exception as e:
            logger.debug(f"获取WBI验证字符串失败: {e}")
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
            orig_type_desc = self._get_forward_type_description(orig_type, orig)

            return {
                'author': orig_author_name,
                'type_desc': orig_type_desc,
                'orig_type': orig_type
            }

        except Exception as e:
            logger.debug(f"解析转发原始信息失败: {e}")
            return None

    def _get_forward_type_description(self, bili_type: str, orig_data: dict = None) -> str:
        """获取转发类型描述"""
        # 基础类型映射
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

        # 如果有原始数据，尝试从major.type获取更精确的类型
        if orig_data and bili_type == 'DYNAMIC_TYPE_AV':
            try:
                modules = orig_data.get('modules', {})
                dynamic_module = modules.get('module_dynamic', {})
                major = dynamic_module.get('major', {})
                major_type = major.get('type')

                # 检查是否是投稿视频
                if major_type == 'MAJOR_TYPE_ARCHIVE':
                    archive = major.get('archive', {})
                    if archive:
                        return '视频'
            except Exception as e:
                logger.debug(f"解析转发视频类型失败: {e}")

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
