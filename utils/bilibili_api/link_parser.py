"""Extract Bilibili video and live room references from message text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal
from urllib.parse import parse_qs, urlparse

import aiohttp
from nonebot.log import logger

BV_PATTERN = re.compile(r"BV1[a-zA-Z0-9]{9}")
AV_PATTERN = re.compile(r"(?:^|[^\w])av(\d+)", re.IGNORECASE)
B23_URL_PATTERN = re.compile(r"https?://(?:www\.)?b23\.tv/[A-Za-z0-9]+", re.IGNORECASE)
BILIBILI_VIDEO_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.)?bilibili\.com/video/(BV1[a-zA-Z0-9]{9}|av\d+)",
    re.IGNORECASE,
)
LIVE_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.)?live\.bilibili\.com(?:/blanc)?/(\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BilibiliRef:
    kind: Literal["video", "live"]
    bvid: str | None = None
    aid: int | None = None
    room_id: int | None = None


def _normalize_bvid(value: str) -> str:
    if value.upper().startswith("BV"):
        return value if value.startswith("BV") else value.upper()
    return value


def _live_room_id_from_url(url: str) -> int | None:
    match = LIVE_URL_PATTERN.search(url)
    if match:
        return int(match.group(1))

    parsed = urlparse(url)
    if "live.bilibili.com" not in parsed.netloc:
        return None

    query = parse_qs(parsed.query)
    for key in ("room_id", "roomId"):
        values = query.get(key)
        if values and str(values[0]).isdigit():
            return int(values[0])

    path_match = re.search(r"/(\d+)", parsed.path)
    if path_match:
        return int(path_match.group(1))

    return None


def _video_ref_from_url(url: str) -> BilibiliRef | None:
    match = BILIBILI_VIDEO_URL_PATTERN.search(url)
    if match:
        ref = match.group(1)
        if ref.lower().startswith("av"):
            return BilibiliRef(kind="video", aid=int(ref[2:]))
        return BilibiliRef(kind="video", bvid=_normalize_bvid(ref))

    path = urlparse(url).path
    bv_match = BV_PATTERN.search(path)
    if bv_match:
        return BilibiliRef(kind="video", bvid=_normalize_bvid(bv_match.group(0)))

    av_match = re.search(r"/video/av(\d+)", path, re.IGNORECASE)
    if av_match:
        return BilibiliRef(kind="video", aid=int(av_match.group(1)))

    bv_in_url = BV_PATTERN.search(url)
    if bv_in_url:
        return BilibiliRef(kind="video", bvid=_normalize_bvid(bv_in_url.group(0)))

    return None


def _ref_from_url(url: str) -> BilibiliRef | None:
    video_ref = _video_ref_from_url(url)
    if video_ref:
        return video_ref

    room_id = _live_room_id_from_url(url)
    if room_id:
        return BilibiliRef(kind="live", room_id=room_id)

    return None


def _request_headers(
    cookie: str | None = None, *, referer: str = "https://www.bilibili.com/"
) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer,
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def resolve_short_url(
    session: aiohttp.ClientSession,
    url: str,
    *,
    cookie: str | None = None,
) -> str | None:
    """Follow b23.tv redirects and return the final URL."""
    try:
        async with session.get(
            url,
            allow_redirects=True,
            headers=_request_headers(cookie),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            return str(response.url)
    except Exception as exc:
        logger.warning(f"解析短链失败: {url}, {exc}")
        return None


def _dedupe_preserve_order(items: Iterable[BilibiliRef]) -> list[BilibiliRef]:
    seen: set[tuple] = set()
    result: list[BilibiliRef] = []
    for item in items:
        key = (
            item.kind,
            item.bvid,
            item.aid,
            item.room_id,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


async def extract_bilibili_refs(
    text: str,
    session: aiohttp.ClientSession,
    *,
    cookie: str | None = None,
    max_count: int = 3,
) -> list[BilibiliRef]:
    """Extract unique video or live room references from plain text."""
    refs: list[BilibiliRef] = []

    for match in BV_PATTERN.finditer(text):
        refs.append(BilibiliRef(kind="video", bvid=_normalize_bvid(match.group(0))))

    for match in AV_PATTERN.finditer(text):
        refs.append(BilibiliRef(kind="video", aid=int(match.group(1))))

    for match in BILIBILI_VIDEO_URL_PATTERN.finditer(text):
        ref = match.group(1)
        if ref.lower().startswith("av"):
            refs.append(BilibiliRef(kind="video", aid=int(ref[2:])))
        else:
            refs.append(BilibiliRef(kind="video", bvid=_normalize_bvid(ref)))

    for match in LIVE_URL_PATTERN.finditer(text):
        refs.append(BilibiliRef(kind="live", room_id=int(match.group(1))))

    for match in B23_URL_PATTERN.finditer(text):
        final_url = await resolve_short_url(session, match.group(0), cookie=cookie)
        if not final_url:
            continue
        parsed = _ref_from_url(final_url)
        if parsed:
            refs.append(parsed)

    return _dedupe_preserve_order(refs)[:max_count]


async def extract_video_refs(
    text: str,
    session: aiohttp.ClientSession,
    *,
    cookie: str | None = None,
    max_count: int = 3,
) -> list[tuple[str | None, int | None]]:
    """Backward-compatible video-only extraction."""
    refs = await extract_bilibili_refs(
        text, session, cookie=cookie, max_count=max_count
    )
    result: list[tuple[str | None, int | None]] = []
    for ref in refs:
        if ref.kind == "video":
            result.append((ref.bvid, ref.aid))
    return result
