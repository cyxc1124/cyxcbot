"""Classify Douyin aweme detail and extract album / Live Photo URLs.

Logic aligned with douyin_parse ``DouyinVideoParser.get_content_type`` /
``extract_image_data``, but:

- operates on unwrapped ``aweme_detail`` (what ``get_video_detail`` returns)
- marks Live vs static **per image** (mixed albums keep order)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from .video_urls import extract_first_url

ContentType = Literal["video", "image"]
MediaKind = Literal["video", "image"]


@dataclass(frozen=True)
class AlbumMediaUrl:
    url: str
    kind: MediaKind  # Live Photo → "video" (mp4); static → "image"


def get_content_type(detail: dict[str, Any]) -> ContentType:
    """Return ``video`` or ``image`` (album / note / Live album)."""
    aweme_type = detail.get("aweme_type", 0)
    try:
        aweme_type = int(aweme_type)
    except TypeError, ValueError:
        aweme_type = 0
    if aweme_type in (0, 4):
        return "video"
    if aweme_type in (2, 68):
        return "image"
    if detail.get("images"):
        return "image"
    return "video"


def _strip_watermark_params(url: str) -> str:
    return url.split("&watermark=")[0].split("&logo_name=")[0]


def _is_live_image(img: dict[str, Any]) -> bool:
    # Reference: live_photo_type / clip_type / embedded video → Live Photo
    return (
        img.get("live_photo_type") == 1
        or img.get("clip_type") == 5
        or bool(img.get("video"))
        or img.get("is_animated") in (True, 1)
        or img.get("animated") in (True, 1)
        or str(img.get("image_type", "")).lower() in ("animated", "live")
        or str(img.get("type", "")).lower() == "animated"
        or img.get("format") == "gif"
    )


def _live_video_url(img: dict[str, Any]) -> Optional[str]:
    video = img.get("video")
    if not isinstance(video, dict):
        return None
    url = extract_first_url(video.get("play_addr")) or extract_first_url(
        video.get("download_addr")
    )
    if not url:
        return None
    return _strip_watermark_params(url)


def _static_image_url(img: dict[str, Any]) -> Optional[str]:
    return (
        extract_first_url(img.get("url_list"))
        or extract_first_url(img.get("download_url_list"))
        or extract_first_url(img.get("url"))
        or extract_first_url(img.get("origin_url"))
    )


def extract_album_urls(detail: dict[str, Any]) -> list[AlbumMediaUrl]:
    """Ordered album URLs; Live Photos use mp4 play_addr (kind=video)."""
    images = detail.get("images") or []
    if not isinstance(images, list):
        return []

    out: list[AlbumMediaUrl] = []
    seen: set[str] = set()
    for img in images:
        if not isinstance(img, dict):
            continue

        url: Optional[str] = None
        kind: MediaKind = "image"
        if _is_live_image(img):
            live_url = _live_video_url(img)
            if live_url:
                url = live_url
                kind = "video"
        if not url:
            url = _static_image_url(img)
            kind = "image"
        if not url:
            continue

        dedupe_key = url.split("?", 1)[0]
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(AlbumMediaUrl(url=url, kind=kind))
    return out


def guess_media_extension(url: str, *, kind: MediaKind) -> str:
    if kind == "video":
        return ".mp4"
    path = url.split("?", 1)[0].lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"
