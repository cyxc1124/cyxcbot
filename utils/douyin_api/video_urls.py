"""Build prioritized video download URL candidates (from downloader_base)."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from .client import DouyinAPIClient

_PLAY_ADDR_KEYS = (
    "play_addr_h264",
    "play_addr_265",
    "play_addr_256",
    "play_addr",
)

_QUALITY_TARGET_WIDTH: dict[str, int] = {
    "1440p": 2560,
    "1080p": 1920,
    "720p": 1280,
    "540p": 960,
    "480p": 854,
    "360p": 640,
}


def download_headers(
    api_client: DouyinAPIClient, *, user_agent: Optional[str] = None
) -> dict[str, str]:
    return {
        "Referer": f"{api_client.BASE_URL}/",
        "Origin": api_client.BASE_URL,
        "Accept": "*/*",
        "User-Agent": user_agent or api_client.headers.get("User-Agent", ""),
    }


def is_watermarked_media_url(url: str) -> bool:
    normalized = url.lower()
    watermark_hints = (
        "tplv-dy-water",
        "dy-water",
        "owner_watermark",
        "watermark_image",
        "watermark=1",
        "playwm",
    )
    return any(hint in normalized for hint in watermark_hints)


def extract_urls(source: Any) -> list[str]:
    if isinstance(source, dict):
        url_list = source.get("url_list") or source.get("urlList")
        if isinstance(url_list, list) and url_list:
            return [item for item in url_list if isinstance(item, str) and item]
    elif isinstance(source, list) and source:
        return [item for item in source if isinstance(item, str) and item]
    elif isinstance(source, str) and source:
        return [source]
    return []


def extract_first_url(source: Any) -> Optional[str]:
    urls = extract_urls(source)
    return urls[0] if urls else None


def _resolution_metrics(
    entry: dict[str, Any], play_addr: dict[str, Any]
) -> tuple[int, int]:
    try:
        width = int(play_addr.get("width") or entry.get("width") or 0)
        height = int(play_addr.get("height") or entry.get("height") or 0)
    except TypeError, ValueError:
        return 0, 0
    if width > 0 and height > 0:
        return min(width, height), width * height
    long_edge = max(width, height)
    if long_edge <= 0:
        return 0, 0
    nearest = min(
        _QUALITY_TARGET_WIDTH.items(),
        key=lambda item: abs(item[1] - long_edge),
    )[0]
    short_edge = int(nearest[:-1])
    return short_edge, long_edge * short_edge


def _find_bit_rate_entry(
    video: dict[str, Any], play_addr: dict[str, Any]
) -> dict[str, Any]:
    entries = video.get("bit_rate") if isinstance(video, dict) else None
    if not isinstance(entries, list):
        return {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("play_addr") is play_addr:
            return entry
    return {}


def _pick_play_addr_by_quality(
    video: dict[str, Any], quality: str = "highest"
) -> Optional[dict[str, Any]]:
    bit_rates = video.get("bit_rate") if isinstance(video, dict) else None
    if not isinstance(bit_rates, list) or not bit_rates:
        return None

    entries: list[tuple[int, int, int, dict[str, Any]]] = []
    for entry in bit_rates:
        if not isinstance(entry, dict):
            continue
        play_addr = entry.get("play_addr")
        if not isinstance(play_addr, dict):
            continue
        try:
            br = int(entry.get("bit_rate") or 0)
        except TypeError, ValueError:
            br = 0
        short_edge, pixels = _resolution_metrics(entry, play_addr)
        entries.append((br, short_edge, pixels, play_addr))
    if not entries:
        return None

    normalised = (quality or "highest").strip().lower()
    if normalised == "lowest":
        entries.sort(key=lambda t: (t[0], t[2]))
        return entries[0][3]
    if normalised in _QUALITY_TARGET_WIDTH:
        target_edge = int(normalised[:-1])
        entries.sort(key=lambda t: (abs(t[1] - target_edge), -t[0], -t[2]))
        return entries[0][3]
    entries.sort(key=lambda t: (-t[2], -t[0], -t[1]))
    return entries[0][3]


def pick_preferred_play_addr(
    video: dict[str, Any], quality: str = "highest"
) -> Optional[dict[str, Any]]:
    preferred = _pick_play_addr_by_quality(video, quality)
    if preferred:
        return preferred
    if not isinstance(video, dict):
        return None
    primary = video.get("play_addr")
    if isinstance(primary, dict) and primary.get("uri"):
        return primary
    for key in _PLAY_ADDR_KEYS:
        candidate = video.get(key)
        if isinstance(candidate, dict) and (
            extract_first_url(candidate) or candidate.get("uri")
        ):
            return candidate
    return None


def _partition_video_candidates(
    api_client: DouyinAPIClient, url_candidates: list[str]
) -> tuple[
    list[tuple[str, dict[str, str]]],
    Optional[str],
    Optional[tuple[str, dict[str, str]]],
]:
    direct: list[tuple[str, dict[str, str]]] = []
    play: Optional[str] = None
    watermarked: Optional[tuple[str, dict[str, str]]] = None

    for candidate in url_candidates:
        is_watermarked = is_watermarked_media_url(candidate)
        if urlparse(candidate).netloc.endswith("douyin.com"):
            if is_watermarked:
                if watermarked is None:
                    watermarked = _sign_play_candidate(api_client, candidate)
                continue
            play = play or candidate
            continue
        if is_watermarked:
            watermarked = watermarked or (candidate, download_headers(api_client))
        else:
            direct.append((candidate, download_headers(api_client)))
    return direct, play, watermarked


def _sign_play_candidate(
    api_client: DouyinAPIClient, candidate: str
) -> tuple[str, dict[str, str]]:
    if "X-Bogus=" not in candidate:
        signed_url, ua = api_client.sign_url(candidate)
        return signed_url, download_headers(api_client, user_agent=ua)
    return candidate, download_headers(api_client)


def _build_signed_play_url(
    api_client: DouyinAPIClient,
    video: dict[str, Any],
    play_addr: dict[str, Any],
    quality: str,
) -> Optional[tuple[str, dict[str, str]]]:
    uri = (
        play_addr.get("uri")
        or video.get("vid")
        or video.get("download_addr", {}).get("uri")
    )
    if not uri:
        return None
    selected_entry = _find_bit_rate_entry(video, play_addr)
    short_edge, _ = _resolution_metrics(selected_entry, play_addr)
    selected_ratio = f"{short_edge}p"
    normalised_quality = quality.strip().lower()
    ratio_map = {"highest": "1080p", "lowest": "540p"}
    fallback_ratio = ratio_map.get(
        normalised_quality,
        normalised_quality if normalised_quality in _QUALITY_TARGET_WIDTH else "1080p",
    )
    ratio = (
        selected_ratio if selected_ratio in _QUALITY_TARGET_WIDTH else fallback_ratio
    )
    params = {
        "video_id": uri,
        "ratio": ratio,
        "line": "0",
        "is_play_url": "1",
        "watermark": "0",
        "source": "PackSourceEnum_PUBLISH",
    }
    signed_url, ua = api_client.build_signed_path("/aweme/v1/play/", params)
    return signed_url, download_headers(api_client, user_agent=ua)


def build_video_url_candidates(
    api_client: DouyinAPIClient,
    aweme_data: dict[str, Any],
    *,
    video_quality: str = "highest",
) -> list[tuple[str, dict[str, str]]]:
    """Priority: direct CDN → signed play → watermarked fallback."""
    video = aweme_data.get("video", {})
    quality = str(video_quality or "highest")
    play_addr = pick_preferred_play_addr(video, quality) or {}
    url_candidates = [c for c in (play_addr.get("url_list") or []) if c]
    url_candidates.sort(key=lambda u: 0 if "watermark=0" in u else 1)

    direct_candidates, play_candidate, watermarked_candidate = (
        _partition_video_candidates(api_client, url_candidates)
    )

    candidates: list[tuple[str, dict[str, str]]] = list(direct_candidates)
    if play_candidate:
        candidates.append(_sign_play_candidate(api_client, play_candidate))
    if candidates:
        return candidates

    constructed = _build_signed_play_url(api_client, video, play_addr, quality)
    if constructed:
        return [constructed]
    if watermarked_candidate:
        return [watermarked_candidate]
    return []
