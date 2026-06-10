"""
直播通知卡片图片生成模块
使用 Pillow 生成开播通知卡片
"""

import asyncio
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import aiohttp
from nonebot.log import logger
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from utils.bilibili_api import RoomInfo, UserInfo

# 渲染倍率（2x 高清）
SCALE = 2

# 卡片逻辑尺寸（设计稿基准），实际渲染 × SCALE
CARD_WIDTH = 450 * SCALE
CARD_PADDING = 20 * SCALE
CARD_RADIUS = 16 * SCALE

# 顶部区域
HEADER_HEIGHT = 80 * SCALE
AVATAR_SIZE = 48 * SCALE

# 封面区域：无封面时使用默认 16:9 占位高度
COVER_DEFAULT_HEIGHT = 230 * SCALE

# 底部区域
FOOTER_HEIGHT = 50 * SCALE

# 颜色
COLOR_BG = (255, 255, 255)
COLOR_BG_LIGHT_PINK = (255, 245, 247)
COLOR_PRIMARY = (255, 158, 181)
COLOR_TEXT_DARK = (51, 51, 51)
COLOR_TEXT_WHITE = (255, 255, 255)
COLOR_LIVE_TAG_BG = (231, 76, 60)
COLOR_END_TAG_BG = (153, 153, 153)
COLOR_COVER_PLACEHOLDER = (255, 228, 233)

# 字体路径候选列表（按优先级）
FONT_CANDIDATES = [
    # Linux (Debian/Ubuntu fonts-noto-cjk)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf",
    # 项目内可选
    str(
        Path(__file__).parent.parent.parent
        / "assets"
        / "fonts"
        / "NotoSansCJK-Regular.ttf"
    ),
    str(
        Path(__file__).parent.parent.parent
        / "assets"
        / "fonts"
        / "NotoSansSC-Regular.otf"
    ),
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

# 全局字体缓存
_font_cache: dict = {}


def _find_font_path() -> str:
    """按优先级查找可用字体路径"""
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "未找到可用中文字体。Docker/Linux 环境请安装 fonts-noto-cjk，"
        "或将字体文件放入 assets/fonts/ 目录。"
    )


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取字体（带缓存）"""
    if size not in _font_cache:
        path = _find_font_path()
        _font_cache[size] = ImageFont.truetype(path, size)
    return _font_cache[size]


def _round_corner_mask(size: tuple, radius: int) -> Image.Image:
    """创建圆角矩形遮罩"""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255
    )
    return mask


def _circle_crop(img: Image.Image, size: int) -> Image.Image:
    """将图片裁剪为圆形"""
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (size - 1, size - 1)], fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def _cover_fit(cover_img: Image.Image, target_w: int) -> Image.Image:
    """按目标宽度等比缩放，保留完整画面（类似 CSS object-fit: contain / width: 100%）"""
    src_w, src_h = cover_img.size
    scale = target_w / src_w
    new_h = int(src_h * scale)
    return cover_img.resize((target_w, new_h), Image.Resampling.LANCZOS)


def _make_avatar_cover(
    avatar_img: Image.Image, target_w: int, target_h: int
) -> Image.Image:
    """封面缺失时，用头像生成模糊背景 + 居中圆形头像的替代封面"""
    bg = avatar_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))

    avatar_size = min(target_w, target_h) // 2
    avatar_circle = _circle_crop(avatar_img, avatar_size)
    x = (target_w - avatar_size) // 2
    y = (target_h - avatar_size) // 2
    bg.paste(avatar_circle, (x, y), avatar_circle)
    return bg


def _truncate_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int = 2,
) -> list[str]:
    """将文本按宽度换行，超出行数用省略号截断"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width:
            if len(lines) >= max_lines - 1:
                current_line = current_line[:-1] + "..." if current_line else "..."
                lines.append(current_line)
                return lines
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines


async def _download_image(url: str, timeout: int = 10) -> Optional[Image.Image]:
    """异步下载图片，失败返回 None"""
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(BytesIO(data)).convert("RGBA")
    except Exception as e:
        logger.warning(f"下载图片失败 {url}: {e}")
    return None


def _draw_card(
    avatar_img: Optional[Image.Image],
    cover_img: Optional[Image.Image],
    streamer_name: str,
    title: str,
    room_id: int,
    live_start_time: int,
    area_label: str = "",
    card_type: str = "start",
    duration_seconds: int = 0,
) -> bytes:
    """同步绘制卡片，返回 PNG bytes"""
    S = SCALE
    # 字体
    font_name = _get_font(18 * S)
    font_area = _get_font(12 * S)
    font_title = _get_font(15 * S)
    font_tag = _get_font(11 * S)
    font_footer = _get_font(12 * S)

    # 计算标题行高
    temp_img = Image.new("RGB", (CARD_WIDTH, 100 * S))
    temp_draw = ImageDraw.Draw(temp_img)
    title_max_w = CARD_WIDTH - CARD_PADDING * 2
    title_lines = _truncate_text(temp_draw, title, font_title, title_max_w, max_lines=2)
    title_line_height = 22 * S
    title_block_height = len(title_lines) * title_line_height + 16 * S

    # 计算封面实际高度
    cover_w = CARD_WIDTH - CARD_PADDING * 2
    if cover_img:
        cover_fitted = _cover_fit(cover_img, cover_w)
        cover_h = cover_fitted.size[1]
    elif avatar_img:
        cover_h = COVER_DEFAULT_HEIGHT
        cover_fitted = _make_avatar_cover(avatar_img, cover_w, cover_h)
    else:
        cover_fitted = None
        cover_h = COVER_DEFAULT_HEIGHT

    # 计算总高度
    card_height = (
        CARD_PADDING
        + HEADER_HEIGHT
        + title_block_height
        + cover_h
        + 12 * S
        + FOOTER_HEIGHT
        + CARD_PADDING
    )

    # 创建画布
    card = Image.new("RGBA", (CARD_WIDTH, card_height), (0, 0, 0, 0))
    mask = _round_corner_mask((CARD_WIDTH, card_height), CARD_RADIUS)

    # 背景：封面模糊放大 + 半透明白色蒙版，保证文字可读
    bg_source = cover_img or avatar_img
    if bg_source:
        bg_blur = bg_source.resize((CARD_WIDTH, card_height), Image.Resampling.LANCZOS)
        bg_blur = bg_blur.filter(
            ImageFilter.GaussianBlur(radius=15 * S)
        )  # 模糊半径：15 轻微 / 30 中等 / 50 强模糊
        overlay = Image.new(
            "RGBA", (CARD_WIDTH, card_height), (255, 255, 255, 120)
        )  # 白色蒙版透明度：120 透出更多色彩 / 180 偏白 / 220 接近纯白
        bg_blur = bg_blur.convert("RGBA")
        bg_blur = Image.alpha_composite(bg_blur, overlay)
        card.paste(bg_blur, (0, 0), mask)
    else:
        bg = Image.new("RGBA", (CARD_WIDTH, card_height), COLOR_BG + (255,))
        card.paste(bg, (0, 0), mask)
    draw = ImageDraw.Draw(card)

    y = CARD_PADDING

    # === 顶部：头像 + 名称 + 职业 + 直播标签 ===
    avatar_x = CARD_PADDING
    avatar_y = y + (HEADER_HEIGHT - AVATAR_SIZE) // 2

    if avatar_img:
        avatar_circle = _circle_crop(avatar_img, AVATAR_SIZE)
        card.paste(avatar_circle, (avatar_x, avatar_y), avatar_circle)
    else:
        draw.ellipse(
            [
                (avatar_x, avatar_y),
                (avatar_x + AVATAR_SIZE - 1, avatar_y + AVATAR_SIZE - 1),
            ],
            fill=COLOR_COVER_PLACEHOLDER,
        )

    text_x = avatar_x + AVATAR_SIZE + 12 * S
    name_y = avatar_y + 4 * S
    draw.text((text_x, name_y), streamer_name, fill=COLOR_TEXT_DARK, font=font_name)

    if area_label:
        area_y = name_y + 24 * S
        draw.text((text_x, area_y), area_label, fill=COLOR_TEXT_DARK, font=font_area)

    # 状态标签
    if card_type == "end":
        tag_label = "已下播"
        tag_bg = COLOR_END_TAG_BG
    else:
        tag_label = "正在直播~"
        tag_bg = COLOR_LIVE_TAG_BG

    tag_text_full = f" {tag_label} "
    tag_bbox = draw.textbbox((0, 0), tag_text_full, font=font_tag)
    tag_w = tag_bbox[2] - tag_bbox[0] + 16 * S
    tag_h = tag_bbox[3] - tag_bbox[1] + 10 * S
    tag_x = CARD_WIDTH - CARD_PADDING - tag_w
    tag_y = avatar_y + (AVATAR_SIZE - tag_h) // 2
    draw.rounded_rectangle(
        [(tag_x, tag_y), (tag_x + tag_w, tag_y + tag_h)], radius=tag_h // 2, fill=tag_bg
    )
    # 小圆点
    dot_r = 3 * S
    dot_x = tag_x + 10 * S
    dot_y = tag_y + tag_h // 2
    draw.ellipse(
        [(dot_x - dot_r, dot_y - dot_r), (dot_x + dot_r, dot_y + dot_r)],
        fill=COLOR_TEXT_WHITE,
    )
    tag_text_x = dot_x + dot_r + 4 * S
    tag_text_y = tag_y + (tag_h - (tag_bbox[3] - tag_bbox[1])) // 2 - 1 * S
    draw.text((tag_text_x, tag_text_y), tag_label, fill=COLOR_TEXT_WHITE, font=font_tag)

    y += HEADER_HEIGHT

    # === 中部：直播标题 ===
    title_y = y + 4 * S
    for line in title_lines:
        draw.text((CARD_PADDING, title_y), line, fill=COLOR_TEXT_DARK, font=font_title)
        title_y += title_line_height
    y += title_block_height

    # === 中部：主视觉区（封面，等比缩放不裁剪） ===
    cover_radius = 8 * S
    if cover_fitted:
        cover_mask = _round_corner_mask((cover_w, cover_h), cover_radius)
        cover_rgba = cover_fitted.convert("RGBA")
        card.paste(cover_rgba, (CARD_PADDING, y), cover_mask)
    else:
        draw.rounded_rectangle(
            [(CARD_PADDING, y), (CARD_PADDING + cover_w, y + cover_h)],
            radius=cover_radius,
            fill=COLOR_COVER_PLACEHOLDER,
        )
    y += cover_h + 12 * S

    # === 底部信息 ===
    footer_left = f"房间号：{room_id}"
    if card_type == "end" and duration_seconds > 0:
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        secs = duration_seconds % 60
        if hours > 0:
            footer_right = f"直播时长：{hours}小时{minutes}分钟{secs}秒"
        elif minutes > 0:
            footer_right = f"直播时长：{minutes}分钟{secs}秒"
        else:
            footer_right = f"直播时长：{secs}秒"
    elif live_start_time > 0:
        time_str = datetime.fromtimestamp(live_start_time).strftime("%Y-%m-%d %H:%M:%S")
        footer_right = f"开播于：{time_str}"
    else:
        footer_right = ""

    draw.text((CARD_PADDING, y), footer_left, fill=COLOR_TEXT_DARK, font=font_footer)

    if footer_right:
        right_bbox = draw.textbbox((0, 0), footer_right, font=font_footer)
        right_w = right_bbox[2] - right_bbox[0]
        draw.text(
            (CARD_WIDTH - CARD_PADDING - right_w, y),
            footer_right,
            fill=COLOR_TEXT_DARK,
            font=font_footer,
        )

    # 下播卡片叠加暗色蒙版，营造"已结束"的视觉感
    if card_type == "end":
        dark_overlay = Image.new(
            "RGBA", (CARD_WIDTH, card_height), (0, 0, 0, 60)
        )  # 暗色蒙版：40 微暗 / 60 适中 / 90 较暗
        card = Image.alpha_composite(card, dark_overlay)

    # 输出 PNG bytes
    output = BytesIO()
    card.save(output, format="PNG")
    return output.getvalue()


async def generate_live_start_card(
    streamer_name: str,
    user_info: Optional[UserInfo],
    room_info: Optional[RoomInfo],
) -> Optional[bytes]:
    """
    生成开播通知卡片图片

    Args:
        streamer_name: 主播名称
        user_info: 主播信息（含头像 URL）
        room_info: 房间信息（含封面 URL、标题、分区等）

    Returns:
        PNG 图片 bytes，失败返回 None
    """
    if not room_info:
        logger.warning("缺少 room_info，无法生成卡片")
        return None

    try:
        face_url = user_info.face if user_info else ""
        cover_url = room_info.cover or ""

        avatar_img, cover_img = await asyncio.gather(
            _download_image(face_url),
            _download_image(cover_url),
        )

        area_parts = []
        if room_info.parent_area_name:
            area_parts.append(room_info.parent_area_name)
        if room_info.area_name:
            area_parts.append(room_info.area_name)
        area_label = " · ".join(area_parts)

        card_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            _draw_card,
            avatar_img,
            cover_img,
            streamer_name,
            room_info.title or "",
            room_info.room_id,
            room_info.live_start_time,
            area_label,
        )

        logger.info(f"开播卡片生成成功，大小: {len(card_bytes)} bytes")
        return card_bytes

    except FileNotFoundError as e:
        logger.error(f"卡片生成失败（字体缺失）: {e}")
        return None
    except Exception as e:
        logger.error(f"卡片生成失败: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return None


async def generate_live_end_card(
    streamer_name: str,
    user_info: Optional[UserInfo],
    room_info: Optional[RoomInfo],
    duration_seconds: int = 0,
) -> Optional[bytes]:
    """
    生成下播通知卡片图片

    Args:
        streamer_name: 主播名称
        user_info: 主播信息（含头像 URL）
        room_info: 房间信息（含封面 URL、标题、分区等）
        duration_seconds: 直播时长（秒）

    Returns:
        PNG 图片 bytes，失败返回 None
    """
    if not room_info:
        logger.warning("缺少 room_info，无法生成下播卡片")
        return None

    try:
        face_url = user_info.face if user_info else ""
        cover_url = room_info.cover or ""

        avatar_img, cover_img = await asyncio.gather(
            _download_image(face_url),
            _download_image(cover_url),
        )

        area_parts = []
        if room_info.parent_area_name:
            area_parts.append(room_info.parent_area_name)
        if room_info.area_name:
            area_parts.append(room_info.area_name)
        area_label = " · ".join(area_parts)

        card_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            _draw_card,
            avatar_img,
            cover_img,
            streamer_name,
            room_info.title or "",
            room_info.room_id,
            room_info.live_start_time,
            area_label,
            "end",
            duration_seconds,
        )

        logger.info(f"下播卡片生成成功，大小: {len(card_bytes)} bytes")
        return card_bytes

    except FileNotFoundError as e:
        logger.error(f"下播卡片生成失败（字体缺失）: {e}")
        return None
    except Exception as e:
        logger.error(f"下播卡片生成失败: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return None
