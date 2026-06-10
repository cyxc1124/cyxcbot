"""
动态数据获取和解析模块
负责直接调用B站API获取动态数据
"""

import aiohttp
import asyncio
import json
import time
from typing import List, Optional
from urllib.parse import urlencode
from nonebot.log import logger

from .dynamic_models import DynamicItem


class DynamicFetcher:
    """B站动态数据获取器"""

    def __init__(self, session: aiohttp.ClientSession, cookie: Optional[str] = None):
        self.session = session
        self.cookie = cookie  # 保存cookie供后续使用
        # B站API请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Referer': 'https://space.bilibili.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def _effective_cookie(self, cookie: Optional[str] = None) -> Optional[str]:
        value = (cookie or self.cookie or "").strip()
        return value or None

    def _request_headers(
        self,
        *,
        cookie: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> dict[str, str]:
        headers = self.headers.copy()
        effective_cookie = self._effective_cookie(cookie)
        if effective_cookie:
            headers["Cookie"] = effective_cookie
        if referer:
            headers["Referer"] = referer
        return headers

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
            request_headers = self._request_headers(
                cookie=cookie,
                referer=f"https://space.bilibili.com/{uid}/dynamic",
            )
            if self._effective_cookie(cookie):
                logger.debug(f"使用 Cookie 进行 B 站动态列表请求: uid={uid}")

            async with self.session.get(
                api_url,
                params=params,
                headers=request_headers,
                timeout=30
            ) as response:

                if response.status != 200:
                    logger.debug(f"B站API请求失败 {uid}: HTTP {response.status}")
                    return None

                response_text = await response.text()
                logger.debug(f"B站API响应长度: {len(response_text)}")

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.debug(f"解析B站API响应失败 {uid}: {e}")
                    logger.debug(f"原始响应: {response_text[:500]}")
                    return None

                # 检查API响应状态
                if data.get('code') != 0:
                    error_msg = data.get('message', '未知错误')
                    logger.debug(f"B站API返回错误 {uid}: {error_msg}")
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
                                logger.debug(f"解析到置顶动态: {pinned_id}")
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
                logger.debug(f"成功获取用户 {uid} 的 {len(dynamics)} 条动态")
                return dynamics, current_pinned_id

        except asyncio.TimeoutError:
            logger.debug(f"B站API请求超时 {uid}")
            return None
        except Exception as e:
            logger.error(f"B站API请求异常 {uid}: {e}")
            return None

    async def fetch_dynamic_detail(
        self,
        dynamic_id: str,
        cookie: Optional[str] = None,
    ) -> Optional[DynamicItem]:
        """Fetch a single dynamic by ID and parse images/text."""
        if not self.session:
            return None

        dynamic_id = str(dynamic_id).strip()
        if not dynamic_id.isdigit():
            logger.warning(f"动态 ID 无效: {dynamic_id!r}")
            return None

        api_url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"
        params = {
            "id": dynamic_id,
            "timezone_offset": "-480",
            "platform": "web",
            "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote",
        }

        request_headers = self._request_headers(
            cookie=cookie,
            referer=f"https://t.bilibili.com/{dynamic_id}",
        )
        if self._effective_cookie(cookie):
            logger.debug(f"使用 Cookie 进行 B 站动态详情请求: id={dynamic_id}")
        else:
            logger.warning(f"获取动态 {dynamic_id} 未配置 Cookie，部分动态可能无法访问")

        try:
            async with self.session.get(
                api_url,
                params=params,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    logger.warning(f"获取动态 {dynamic_id} 失败: HTTP {response.status}")
                    return None

                data = await response.json()
                if data.get("code") != 0:
                    logger.warning(
                        f"获取动态 {dynamic_id} 失败: {data.get('message', '未知错误')}"
                    )
                    return None

                item = (data.get("data") or {}).get("item")
                if not item:
                    logger.warning(f"动态 {dynamic_id} 不存在或响应为空")
                    return None

                return await self._parse_dynamic_item(item, uid="0", is_pinned=False)
        except asyncio.TimeoutError:
            logger.warning(f"获取动态 {dynamic_id} 超时")
            return None
        except Exception as exc:
            logger.error(f"获取动态 {dynamic_id} 异常: {exc}")
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

            # 优先尝试从author子对象获取（主动态的结构）
            author_info = author_module.get('author', {})
            author_uid = author_info.get('mid')

            # 如果没有，则直接从module_author获取（转发动态的结构）
            if not author_uid:
                author_uid = author_module.get('mid', uid)

            # 暂时不获取用户名，只保存UID，在需要推送时再获取
            name = f"UP主_{author_uid}"  # 临时占位符，推送时会被替换

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

            content = ""
            body_text = ""
            title = ""
            images: List[str] = []
            module_dynamic = modules.get('module_dynamic', {})

            # 特殊处理转发动态 - 需要解析原始动态信息用于描述
            if bili_dynamic_type == 'DYNAMIC_TYPE_FORWARD':
                orig_info = self._extract_forward_orig_info(item)
                if orig_info:
                    # 判断是否转发自己的内容
                    orig_author_uid = orig_info.get('author_uid')
                    if orig_author_uid and str(orig_author_uid) == str(author_uid):
                        # 转发自己的内容
                        content = f"转发了自己的{orig_info['type_desc']}"
                    else:
                        # 转发别人的内容
                        content = f"转发了【{orig_info['author']}】的{orig_info['type_desc']}"

                orig = item.get('orig')
                if orig and isinstance(orig, dict):
                    orig_modules = orig.get('modules', {})
                    orig_dynamic = orig_modules.get('module_dynamic', {})
                    body_text, title = self._extract_text_from_module_dynamic(orig_dynamic)
                    images = self._extract_images_from_major(
                        orig_dynamic.get('major') if isinstance(orig_dynamic, dict) else None
                    )
            else:
                body_text, title = self._extract_text_from_module_dynamic(module_dynamic)
                images = self._extract_images_from_major(
                    module_dynamic.get('major') if isinstance(module_dynamic, dict) else None
                )

            logger.debug(
                f"动态 {dynamic_id}: B站类型={bili_dynamic_type}, 映射类型={dynamic_type}, "
                f"UID={author_uid}, 图片数={len(images)}"
            )

            # 创建DynamicItem对象
            dynamic_item = DynamicItem(
                dynamic_id=dynamic_id,
                uid=int(author_uid),
                name=name,
                timestamp=timestamp,
                dynamic_type=dynamic_type,
                title=title,
                content=content,
                body_text=body_text,
                images=images,
                author_type=author_type,
                is_pinned=is_pinned
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
        from . import wbi
        
        try:
            user_info_url = "https://api.bilibili.com/x/space/wbi/acc/info"

            # 参数
            params = {
                'mid': uid,
                'token': '',
                'platform': 'web',
                'web_location': '1550101'
            }

            # 使用公共 WBI 模块签名
            signed_query = await wbi.sign_params(self.session, params, self.cookie)
            
            if signed_query:
                url = f"{user_info_url}?{signed_query}"
            else:
                # 降级：不使用签名
                url = user_info_url
                logger.debug("无法获取WBI签名，尝试无签名请求")

            # 请求头
            user_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
                'Referer': f'https://space.bilibili.com/{uid}/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
            }

            if self.cookie:
                user_headers['Cookie'] = self.cookie

            logger.debug(f"获取UP主 {uid} 信息，请求URL: {url[:80]}...")

            if signed_query:
                async with self.session.get(url, headers=user_headers, timeout=10) as response:
                    return await self._parse_user_info_response(response, uid)
            else:
                async with self.session.get(url, params=params, headers=user_headers, timeout=10) as response:
                    return await self._parse_user_info_response(response, uid)

        except Exception as e:
            logger.debug(f"获取UP主信息异常 {uid}: {e}")
            return None
    
    async def _parse_user_info_response(self, response, uid: str) -> Optional[str]:
        """解析用户信息响应"""
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


    @staticmethod
    def _normalize_image_url(url: str) -> str:
        """规范化图片 URL"""
        if not url:
            return ""
        url = url.split("@")[0]
        if url.startswith("//"):
            return "https:" + url
        return url

    @classmethod
    def _dedupe_images(cls, images: List[str]) -> List[str]:
        """去重并保持顺序"""
        seen = set()
        result = []
        for url in images:
            normalized = cls._normalize_image_url(url)
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    @classmethod
    def _extract_images_from_major(cls, major: Optional[dict]) -> List[str]:
        """从动态主体中提取图片 URL"""
        if not major or not isinstance(major, dict):
            return []

        images: List[str] = []

        draw = major.get("draw")
        if isinstance(draw, dict):
            for item in draw.get("items") or []:
                if isinstance(item, dict) and item.get("src"):
                    images.append(item["src"])

        opus = major.get("opus")
        if isinstance(opus, dict):
            for pic in opus.get("pics") or []:
                if isinstance(pic, dict) and pic.get("url"):
                    images.append(pic["url"])

        archive = major.get("archive")
        if isinstance(archive, dict) and archive.get("cover"):
            images.append(archive["cover"])

        article = major.get("article")
        if isinstance(article, dict):
            for cover in article.get("covers") or []:
                if cover:
                    images.append(cover)
            if not article.get("covers") and article.get("cover"):
                images.append(article["cover"])

        return cls._dedupe_images(images)

    @staticmethod
    def _extract_text_from_module_dynamic(module_dynamic: Optional[dict]) -> tuple[str, str]:
        """从 module_dynamic 中提取正文和标题"""
        if not module_dynamic or not isinstance(module_dynamic, dict):
            return "", ""

        text_parts: List[str] = []
        title = ""

        desc = module_dynamic.get("desc")
        if isinstance(desc, dict):
            desc_text = (desc.get("text") or "").strip()
            if desc_text:
                text_parts.append(desc_text)

        major = module_dynamic.get("major")
        if isinstance(major, dict):
            opus = major.get("opus")
            if isinstance(opus, dict):
                opus_title = (opus.get("title") or "").strip()
                if opus_title:
                    title = opus_title
                summary = opus.get("summary")
                if isinstance(summary, dict):
                    summary_text = (summary.get("text") or "").strip()
                    if summary_text and summary_text not in text_parts:
                        text_parts.append(summary_text)

            archive = major.get("archive")
            if isinstance(archive, dict):
                archive_title = (archive.get("title") or "").strip()
                if archive_title:
                    if not title:
                        title = archive_title
                    if archive_title not in text_parts:
                        text_parts.append(archive_title)
                archive_desc = (archive.get("desc") or "").strip()
                if archive_desc and archive_desc not in text_parts:
                    text_parts.append(archive_desc)

            article = major.get("article")
            if isinstance(article, dict):
                article_title = (article.get("title") or "").strip()
                if article_title:
                    if not title:
                        title = article_title
                    if article_title not in text_parts:
                        text_parts.append(article_title)

        return "\n".join(text_parts), title

    def _extract_forward_orig_info(self, item: dict) -> Optional[dict]:
        """提取转发动态的原始信息"""
        try:
            # 转发动态的orig信息直接在item根级别
            orig = item.get('orig')

            if not orig:
                return None

            # 提取原始动态的作者信息
            # 注意：转发动态的orig中，作者信息可能有两种结构
            orig_modules = orig.get('modules', {})
            orig_author = orig_modules.get('module_author', {})

            # 优先尝试从author子对象获取（主动态的结构）
            orig_author_info = orig_author.get('author', {})
            orig_author_name = orig_author_info.get('name')
            orig_author_uid = orig_author_info.get('mid')

            # 如果没有，则直接从module_author获取（orig中的结构）
            if not orig_author_name:
                orig_author_name = orig_author.get('name', '未知用户')
                orig_author_uid = orig_author.get('mid')

            # 提取原始动态的类型
            orig_type = orig.get('type', 'DYNAMIC_TYPE_UNKNOWN')
            orig_type_desc = self._get_forward_type_description(orig_type, orig)

            return {
                'author': orig_author_name,
                'author_uid': orig_author_uid,
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

        logger.debug(f"获取转发类型描述: bili_type={bili_type}, has_orig_data={orig_data is not None}")

        # 如果有原始数据，尝试从major.type获取更精确的类型
        if orig_data and bili_type == 'DYNAMIC_TYPE_AV':
            try:
                # 直接检查major.type，简化逻辑
                major_type = orig_data.get('modules', {}).get('module_dynamic', {}).get('major', {}).get('type')

                logger.debug(f"转发视频检查: major_type={major_type}")

                # 检查是否是投稿视频
                if major_type == 'MAJOR_TYPE_ARCHIVE':
                    logger.debug("确认是投稿视频，返回'视频'")
                    return '视频'
                elif major_type:
                    logger.debug(f"其他major_type: {major_type}")
                else:
                    logger.debug("没有找到major.type")
            except Exception as e:
                logger.debug(f"解析转发视频类型失败: {e}")
                import traceback
                logger.debug(f"异常详情: {traceback.format_exc()}")

        result = type_descriptions.get(bili_type, '动态')
        logger.debug(f"返回转发类型描述: {result}")
        return result

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
