"""Extract aweme_id from Douyin video URLs."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from nonebot.log import logger

from .validators import parse_url_type


def extract_video_id(url: str) -> Optional[str]:
    match = re.search(r"/video/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"modal_id=(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"/(?:note|gallery|slides)/(\d+)", url)
    if match:
        return match.group(1)
    return None


def parse_video_url(url: str) -> Optional[dict[str, Any]]:
    """Parse a resolved Douyin URL into ``{type, aweme_id, original_url}``."""
    url_type = parse_url_type(url)
    if url_type not in {"video", "gallery"}:
        if url_type == "short":
            logger.warning("短链尚未解析，无法提取 aweme_id")
        return None

    aweme_id = extract_video_id(url)
    if not aweme_id:
        # modal_id already covered; try query again for safety
        qs = parse_qs(urlparse(url).query)
        modal_ids = qs.get("modal_id", [])
        if modal_ids and modal_ids[0].strip().isdigit():
            aweme_id = modal_ids[0].strip()
    if not aweme_id:
        return None
    return {
        "original_url": url,
        "type": "video",
        "aweme_id": aweme_id,
    }
