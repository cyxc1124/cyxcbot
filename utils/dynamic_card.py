"""Render API-backed dynamic cards without loading Bilibili webpages."""

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import aiohttp
import qrcode
from material_color_utilities import Hct, TonalPalette, prominent_colors_from_image
from nonebot.log import logger
from PIL import Image, ImageDraw, ImageFont, ImageOps

from utils.bilibili_api.dynamic_models import DynamicItem

MAX_ASSET_BYTES = 10 * 1024 * 1024


def monet_palette(image: Image.Image | None) -> tuple[str, str, str]:
    """Monet: scored image seed → HCT tonal palette, ordered dark to light."""
    colors = (
        prominent_colors_from_image(image.convert("RGBA").resize((128, 128)))
        if image
        else []
    )
    seed = Hct(colors[0] if len(colors) else "#6750a4")
    palette = TonalPalette(seed.hue, min(seed.chroma, 36))
    return tuple(palette.get(tone) for tone in (65, 90, 96))


def _font(size: int):
    for path in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise RuntimeError("动态卡片需要 Noto CJK 或 PingFang 中文字体")


async def _asset(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    # API media must stay on Bilibili's CDN; never follow arbitrary redirects.
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme not in ("http", "https") or not host.endswith(".hdslb.com"):
        return None
    # Bilibili still returns HTTP media URLs; fetch approved CDN assets over TLS.
    url = parsed._replace(scheme="https").geturl()
    try:
        async with session.get(url, allow_redirects=False) as response:
            if response.status != 200:
                return None
            data = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                data.extend(chunk)
                if len(data) > MAX_ASSET_BYTES:
                    return None

        def decode():
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > 20_000_000:
                    return None
                image.thumbnail((1400, 1400))
                return image.convert("RGB")

        return await asyncio.to_thread(decode)
    except aiohttp.ClientError, TimeoutError, OSError, Image.DecompressionBombError:
        logger.debug("动态卡片素材不可用")
        return None


def _draw_card(
    dynamic: DynamicItem,
    avatar,
    pictures,
    color_source: Literal["image", "avatar"] = "image",
) -> bytes:
    seed = (
        avatar if color_source == "avatar" else next((p for p in pictures if p), avatar)
    )
    dark, surface, light = monet_palette(seed)
    font, small, heading = _font(30), _font(24), _font(36)
    lines = []
    # shortcut: one card shows at most 6000 characters and nine images; use the QR for the full post.
    text = "\n".join(
        filter(
            None,
            (dynamic.content, dynamic.forward_text, dynamic.title, dynamic.body_text),
        )
    )
    if len(text) > 6000:
        text = text[:6000] + "\n……正文过长，扫码查看完整动态"
    if len(dynamic.images) > 9:
        text += "\n更多配图请扫码查看"
    for paragraph in (text or dynamic.get_type_description()).split("\n"):
        line = ""
        for char in paragraph:
            if font.getlength(line + char) > 890:
                lines.append(line)
                line = ""
            line += char
        lines.append(line)
    if any(picture is None for picture in pictures):
        raise ValueError("动态配图不完整，回退到原图投递")
    pictures = [p for p in pictures if p is not None]
    cols = 1 if len(pictures) == 1 else 3
    tile = 890 if cols == 1 else 286
    image_height = (
        min(640, round(tile * pictures[0].height / pictures[0].width))
        if cols == 1 and pictures
        else tile
    )
    rows = (len(pictures) + cols - 1) // cols
    media_y = 270 + len(lines) * 46
    footer_y = media_y + rows * (image_height + 16) + 24
    height = footer_y + 200
    card = Image.new("RGB", (1040, height))
    draw = ImageDraw.Draw(card)
    start, end = (
        Image.new("RGB", (1, 1), dark).getpixel((0, 0)),
        Image.new("RGB", (1, 1), light).getpixel((0, 0)),
    )
    for y in range(height):
        draw.line(
            (0, y, 1040, y),
            fill=tuple(
                round(a + (b - a) * y / (height - 1)) for a, b in zip(start, end)
            ),
        )
    draw.rounded_rectangle((28, 82, 1012, height - 28), radius=22, fill=surface)
    draw.rounded_rectangle((48, 26, 240, 100), radius=10, fill=light)
    kind = {1: "转发", 2: "图文", 4: "文字", 8: "视频", 64: "专栏"}.get(
        dynamic.type, "动态"
    )
    draw.text((76, 38), kind, font=heading, fill="#382e3a")
    draw.text((980, 42), str(dynamic.id), font=small, fill="#241e28", anchor="ra")
    if avatar:
        avatar = ImageOps.fit(avatar, (88, 88))
        mask = Image.new("L", (88, 88))
        ImageDraw.Draw(mask).ellipse((0, 0, 88, 88), fill=255)
        card.paste(avatar, (72, 122), mask)
    draw.text((184, 126), dynamic.name[:20], font=heading, fill="#241e28")
    draw.text((184, 180), dynamic.format_beijing_time(), font=small, fill="#514653")
    for i, line in enumerate(lines):
        draw.text((74, 248 + i * 46), line, font=font, fill="#241e28")
    for i, picture in enumerate(pictures):
        box = (tile, image_height)
        fitted = (
            ImageOps.contain(picture, box) if cols == 1 else ImageOps.fit(picture, box)
        )
        card.paste(
            fitted,
            (
                74 + (i % cols) * (tile + 16),
                media_y + (i // cols) * (image_height + 16),
            ),
        )
    draw.rounded_rectangle((66, footer_y, 974, height - 60), radius=22, fill=light)
    stats = dynamic.stats
    draw.text(
        (90, footer_y + 52),
        f"赞 {stats.get('like', 0)}    评论 {stats.get('comment', 0)}    转发 {stats.get('forward', 0)}",
        font=small,
        fill="#514653",
    )
    qr = qrcode.make(dynamic.url, box_size=4, border=2).convert("RGB")
    qr.thumbnail((112, 112), Image.Resampling.NEAREST)
    card.paste(qr, (810, footer_y + 16))
    out = BytesIO()
    card.save(out, "PNG")
    return out.getvalue()


async def render_dynamic_card(
    dynamic: DynamicItem, *, color_source: Literal["image", "avatar"] = "image"
) -> bytes:
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=15),
        headers={"Referer": "https://www.bilibili.com/"},
    ) as session:
        assets = await asyncio.gather(
            *(_asset(session, url) for url in [dynamic.avatar, *dynamic.images[:9]])
        )
    return await asyncio.to_thread(
        _draw_card, dynamic, assets[0], assets[1:], color_source
    )
