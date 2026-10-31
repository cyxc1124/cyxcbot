"""Prepare Douyin replies within the official QQ passive-message budget."""

import asyncio
import math
import uuid
from pathlib import Path

from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.log import logger
from PIL import Image, ImageDraw, ImageOps


def _image_path(segment: MessageSegment) -> Path:
    value = str(segment.data.get("file", ""))
    return Path.from_uri(value) if value.startswith("file:") else Path(value)


def _album_preview(images: list[MessageSegment], directory: Path) -> Path:
    columns = min(4, math.ceil(math.sqrt(len(images))))
    rows = math.ceil(len(images) / columns)
    cell = 320
    preview = Image.new("RGB", (columns * cell, rows * cell), "white")
    draw = ImageDraw.Draw(preview)
    for index, segment in enumerate(images):
        with Image.open(_image_path(segment)) as source:
            if source.width * source.height > 20_000_000:
                raise ValueError("图片像素数过大，不在本地生成拼图")
            source.draft("RGB", (cell - 16, cell - 40))
            thumbnail = ImageOps.exif_transpose(source)
            thumbnail.thumbnail((cell - 16, cell - 40))
            x, y = (index % columns) * cell, (index // columns) * cell
            preview.paste(
                thumbnail.convert("RGB"), (x + (cell - thumbnail.width) // 2, y + 8)
            )
            draw.text((x + 8, y + cell - 24), str(index + 1), fill="black")
    path = directory / f"douyin_preview_{uuid.uuid4().hex}.jpg"
    try:
        preview.save(path, "JPEG", quality=85)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


async def prepare_official_reply(
    message: Message, remaining: int, directory: Path
) -> tuple[Message, list[Path]]:
    if remaining <= 0:
        return Message(), []
    media = [segment for segment in message if segment.type in {"image", "video"}]
    caption = message.extract_plain_text()
    generated = []
    images = [segment for segment in media if segment.type == "image"]
    if (
        remaining > 1
        and len(images) > 1
        and len(media) + bool(caption.strip()) > remaining
    ):
        try:
            # 等渲染线程写完再响应取消，让 finally 能清理生成的预览文件。
            render = asyncio.create_task(
                asyncio.to_thread(_album_preview, images, directory)
            )
            try:
                path = await asyncio.shield(render)
            except asyncio.CancelledError:
                try:
                    while not render.done():
                        try:
                            await asyncio.shield(render)
                        except asyncio.CancelledError:
                            continue
                    render.result().unlink(missing_ok=True)
                except Exception:
                    logger.warning("取消抖音预览渲染时清理失败")
                raise
            generated.append(path)
            media = [MessageSegment.image(path.resolve())] + [
                segment for segment in media if segment.type != "image"
            ]
            caption = f"图集共 {len(images)} 张静态图片，已合成预览。\n{caption}"
        except OSError, ValueError, Image.DecompressionBombError:
            logger.warning("抖音图集合成预览失败，将按官方回复预算回传原媒体")
    limit = remaining - 1 if caption.strip() or len(media) > remaining else remaining
    omitted = len(media) - limit
    if omitted > 0:
        caption = f"官方 Bot 回复次数有限，另有 {omitted} 项媒体请在抖音原作品查看。\n{caption}"
    parts = media[:limit]
    if caption.strip():
        parts.append(MessageSegment.text(caption))
    return Message(parts), generated
