"""
B站 WBI 签名模块
统一的 WBI 签名实现，供所有需要 B站 API 签名的模块使用

参考：
- blrec 的 wbi.py 实现
- RSSHub 的实现
"""

import hashlib
import time
from typing import Any, Dict, Optional

import aiohttp
from nonebot.log import logger

# WBI 混淆数组（固定，从B站JS提取）
# 注意：blrec 只取前32位，RSSHub 取64位
MIXIN_KEY_MAPPING = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]

# 缓存 WBI Key（全局共享）
_wbi_key_cache: Optional[str] = None
_wbi_key_expire: float = 0


def extract_key(url: str) -> str:
    """从URL中提取key（文件名不含扩展名）"""
    return url.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def make_key(img_key: str, sub_key: str) -> str:
    """
    生成混淆后的key

    Args:
        img_key: 从 img_url 提取的 key
        sub_key: 从 sub_url 提取的 key

    Returns:
        混淆后的32字符key
    """
    raw_key = (img_key + sub_key).encode()
    # 按照混淆数组重新排列，取前32个
    result = []
    for idx in MIXIN_KEY_MAPPING:
        if idx < len(raw_key):
            result.append(raw_key[idx])
    return bytes(result[:32]).decode()


def encode_value(value: str) -> str:
    """
    URL编码值（按B站规则）
    - 过滤特殊字符 !'()*
    - 保留 ASCII 字母数字和 -_.~
    - 其他字符转为 %XX 格式
    """
    chars = []
    for c in value:
        if c in "!'()*":
            continue
        if (c.isascii() and c.isalnum()) or c in "-_.~":
            chars.append(c)
        else:
            for b in c.encode():
                chars.append(f"%{b:02X}")
    return "".join(chars)


def build_signed_query(key: str, params: Dict[str, Any]) -> str:
    """
    构建带签名的查询字符串

    Args:
        key: WBI 混淆后的 key
        params: 请求参数字典

    Returns:
        签名后的查询字符串（包含 wts 和 w_rid）
    """
    ts = int(time.time())

    # 复制参数并添加时间戳
    params_list = [(k, str(v)) for k, v in params.items()]
    params_list.append(("wts", str(ts)))

    # 按 key 排序
    params_list.sort(key=lambda p: p[0])

    # 构建查询字符串
    parts = []
    for name, value in params_list:
        parts.append(f"{name}={encode_value(value)}")
    query = "&".join(parts)

    # 计算签名
    sign = hashlib.md5((query + key).encode()).hexdigest()
    query += f"&w_rid={sign}"

    return query


def build_signed_params_str(key: str, params_str: str) -> str:
    """
    对字符串格式的参数进行签名（兼容旧接口）

    Args:
        key: WBI 混淆后的 key
        params_str: 参数字符串，如 "foo=1&bar=2"

    Returns:
        签名后的参数字符串
    """
    # 解析参数字符串
    param_dict = {}
    for param in params_str.split("&"):
        if "=" in param:
            k, v = param.split("=", 1)
            param_dict[k] = v

    return build_signed_query(key, param_dict)


async def get_wbi_key(
    session: aiohttp.ClientSession,
    cookie: Optional[str] = None,
    force_refresh: bool = False,
) -> Optional[str]:
    """
    获取 WBI Key（带缓存）

    Args:
        session: aiohttp 会话
        cookie: B站 Cookie（可选，用于提高成功率）
        force_refresh: 是否强制刷新缓存

    Returns:
        混淆后的 WBI Key，失败返回 None
    """
    global _wbi_key_cache, _wbi_key_expire

    # 检查缓存（非强制刷新时）
    if not force_refresh and _wbi_key_cache and time.time() < _wbi_key_expire:
        logger.debug(f"使用缓存的WBI Key: {_wbi_key_cache[:8]}...")
        return _wbi_key_cache

    try:
        # 获取导航信息
        url = "https://api.bilibili.com/x/web-interface/nav"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with session.get(url, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                logger.warning(f"获取WBI Key失败: HTTP {resp.status}")
                return None

            data = await resp.json()

            if data.get("code") != 0:
                logger.warning(f"获取WBI Key失败: {data.get('message')}")
                return None

            wbi_img = data.get("data", {}).get("wbi_img", {})
            img_url = wbi_img.get("img_url", "")
            sub_url = wbi_img.get("sub_url", "")

            if not img_url or not sub_url:
                logger.warning("获取WBI Key失败: wbi_img 数据不完整")
                return None

            # 提取并混淆key
            img_key = extract_key(img_url)
            sub_key = extract_key(sub_url)
            wbi_key = make_key(img_key, sub_key)

            # 缓存（10分钟）
            _wbi_key_cache = wbi_key
            _wbi_key_expire = time.time() + 600

            logger.debug(f"获取WBI Key成功: {wbi_key[:8]}...")
            return wbi_key

    except Exception as e:
        logger.warning(f"获取WBI Key异常: {e}")
        return None


async def sign_params(
    session: aiohttp.ClientSession, params: Dict[str, Any], cookie: Optional[str] = None
) -> Optional[str]:
    """
    对参数进行WBI签名

    Args:
        session: aiohttp 会话
        params: 请求参数字典
        cookie: B站 Cookie（可选）

    Returns:
        签名后的查询字符串，失败返回 None
    """
    wbi_key = await get_wbi_key(session, cookie)
    if not wbi_key:
        return None

    return build_signed_query(wbi_key, params)


async def sign_params_str(
    session: aiohttp.ClientSession, params_str: str, cookie: Optional[str] = None
) -> Optional[str]:
    """
    对字符串格式的参数进行WBI签名（兼容旧接口）

    Args:
        session: aiohttp 会话
        params_str: 参数字符串，如 "foo=1&bar=2"
        cookie: B站 Cookie（可选）

    Returns:
        签名后的参数字符串，失败返回原始字符串
    """
    wbi_key = await get_wbi_key(session, cookie)
    if not wbi_key:
        return params_str  # 降级返回原始参数

    return build_signed_params_str(wbi_key, params_str)
