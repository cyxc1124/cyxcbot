"""Bound images to what every supported vision API accepts."""

from __future__ import annotations

import base64
from functools import cache
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from .client import VisionAPIError, VisionImage

_DIRECT_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
_RESIZABLE_MODES = frozenset({"RGB", "RGBA", "L", "LA"})
MAX_EDGE = 2048
# Anthropic 单图上限 5 MB（按 base64 计），原图超过时缩放重编码。
MAX_DIRECT_BYTES = 3_500_000
_RESIZE_STEPS = ((MAX_EDGE, 90), (1568, 85), (1024, 75))


def _encode(data: bytes, media_type: str) -> VisionImage:
    return VisionImage(media_type, base64.b64encode(data).decode("ascii"))


def prepare_vision_image(data: bytes) -> VisionImage:
    """Send small PNG/JPEG/WebP as-is; otherwise the first frame as bounded JPEG."""
    try:
        with Image.open(BytesIO(data)) as image:
            media_type = _DIRECT_FORMATS.get(image.format or "")
            if (
                media_type
                and not getattr(image, "is_animated", False)
                and max(image.size) <= MAX_EDGE
                and len(data) <= MAX_DIRECT_BYTES
            ):
                return _encode(data, media_type)
            image.seek(0)
            # 先缩小再转 RGBA，避免 2500 万像素原图整张展开成 RGBA。
            frame = image if image.mode in _RESIZABLE_MODES else image.convert("RGBA")
            frame.thumbnail((MAX_EDGE, MAX_EDGE))
            frame = frame.convert("RGBA")
        for edge, quality in _RESIZE_STEPS:
            resized = frame.copy()
            resized.thumbnail((edge, edge))
            canvas = Image.new("RGB", resized.size, (255, 255, 255))
            canvas.paste(resized, mask=resized.getchannel("A"))
            buffer = BytesIO()
            canvas.save(buffer, format="JPEG", quality=quality)
            if buffer.tell() <= MAX_DIRECT_BYTES:
                return _encode(buffer.getvalue(), "image/jpeg")
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ):
        pass
    raise VisionAPIError("图片无法转换为视觉模型可读取的格式。")


@cache
def sample_image() -> VisionImage:
    """Small generated picture for connectivity tests; no user image is uploaded."""
    radial = Image.radial_gradient("L")
    linear = Image.linear_gradient("L")
    image = Image.merge("RGB", (radial, linear, linear.rotate(90)))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return _encode(buffer.getvalue(), "image/png")
