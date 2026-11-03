"""Download quoted QQ images without re-encoding their provenance metadata."""

from io import BytesIO
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 20 * 1024 * 1024
_FORMATS = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


class ImageDetectionError(ValueError):
    pass


def qq_image_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        allowed = host.endswith(".qpic.cn") or host in {
            "multimedia.nt.qq.com",
            "multimedia.nt.qq.com.cn",
        }
        if (
            parsed.scheme not in {"http", "https"}
            or not allowed
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 80, 443}
        ):
            raise ValueError
    except ValueError:
        raise ImageDetectionError(
            "图片下载地址不可用，请引用 QQ 中的一张原图。"
        ) from None
    return urlunsplit(("https", host, parsed.path, parsed.query, ""))


def image_media_type(data: bytes) -> str:
    try:
        with Image.open(BytesIO(data)) as image:
            media_type = _FORMATS.get(image.format)
            if not media_type:
                raise ImageDetectionError("仅支持 PNG、JPEG、WebP 和 GIF 图片。")
            if image.width * image.height > 25_000_000:
                raise ImageDetectionError("图片超过 2500 万像素，请选择较小的原图。")
            image.verify()
            return media_type
    except UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError:
        raise ImageDetectionError("无法读取图片，文件可能已损坏。") from None


async def download_image(url: str) -> bytes:
    url = qq_image_url(url)
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30), auto_decompress=False
    ) as session:
        async with session.get(url, allow_redirects=False) as response:
            if response.status != 200:
                raise ImageDetectionError("图片下载失败或地址已过期，请重新发送原图。")
            if (
                response.content_length is not None
                and response.content_length > MAX_IMAGE_BYTES
            ):
                raise ImageDetectionError("图片超过 20 MiB，无法检测。")
            data = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ImageDetectionError("图片超过 20 MiB，无法检测。")
            return bytes(data)
