"""Parse X API media attachments into image/video items."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import TweetMediaItem


def pick_mp4_variant(media: dict) -> str | None:
    """Pick highest-bitrate video/mp4 URL from media.variants."""
    variants = media.get("variants") or []
    best_url: str | None = None
    best_bitrate = -1
    for item in variants:
        if not isinstance(item, dict):
            continue
        if str(item.get("content_type") or "") != "video/mp4":
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        try:
            bitrate = int(item.get("bit_rate") or 0)
        except TypeError, ValueError:
            bitrate = 0
        if bitrate >= best_bitrate:
            best_bitrate = bitrate
            best_url = url
    return best_url


def media_items_for_tweet(
    tweet: dict, media_by_key: Dict[str, dict]
) -> List[TweetMediaItem]:
    """Build typed media items; video/gif use mp4 variant, else preview/image URL."""
    attachments = tweet.get("attachments") or {}
    keys = attachments.get("media_keys") or []
    items: List[TweetMediaItem] = []
    for key in keys:
        media = media_by_key.get(str(key))
        if not media:
            continue
        mtype = str(media.get("type") or "").strip().lower()
        if mtype in {"video", "animated_gif"}:
            video_url = pick_mp4_variant(media)
            if video_url:
                items.append(TweetMediaItem(kind="video", url=video_url))
                continue
            preview = str(media.get("preview_image_url") or "").strip()
            if preview:
                items.append(TweetMediaItem(kind="image", url=preview))
            continue
        url = str(media.get("url") or media.get("preview_image_url") or "").strip()
        if url:
            items.append(TweetMediaItem(kind="image", url=url))
    return items


def media_urls_for_tweet(tweet: dict, media_by_key: Dict[str, dict]) -> List[str]:
    """Image/preview URLs for monitor push (videos fall back to preview)."""
    attachments = tweet.get("attachments") or {}
    keys = attachments.get("media_keys") or []
    urls: List[str] = []
    for key in keys:
        media = media_by_key.get(str(key))
        if not media:
            continue
        url = media.get("url") or media.get("preview_image_url")
        if url:
            urls.append(str(url))
    return urls


def index_media(includes: Any) -> Dict[str, dict]:
    if not isinstance(includes, dict):
        return {}
    media_list = includes.get("media") or []
    result: Dict[str, dict] = {}
    for item in media_list:
        if isinstance(item, dict) and item.get("media_key"):
            result[str(item["media_key"])] = item
    return result
