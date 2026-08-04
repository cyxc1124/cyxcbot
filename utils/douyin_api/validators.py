"""Douyin URL helpers (short-link detection + share-text extraction)."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

SHORT_URL_HOSTS = (
    "v.douyin.com",
    "v.iesdouyin.com",
    "iesdouyin.com",
)

_URL_RE = re.compile(
    r"(?:https?://)?(?:(?:www|v|www\.ies|ies)?\.?douyin\.com|v\.iesdouyin\.com)"
    r"/[^\s<>\"'，。！？；：、]+",
    re.IGNORECASE,
)


def _host_matches(host: str, base: str) -> bool:
    return host == base or host.endswith("." + base)


def _is_douyin_web_host(host: str) -> bool:
    return _host_matches(host, "douyin.com") or _host_matches(host, "iesdouyin.com")


def is_short_url(url: str) -> bool:
    """判断是否为需要预先解析的短链。"""
    if not url:
        return False
    candidate = url.strip()
    lowered = candidate.lower()
    for scheme in ("https://", "http://"):
        if lowered.startswith(scheme):
            lowered = lowered[len(scheme) :]
            break
    for host in SHORT_URL_HOSTS:
        if lowered.startswith(f"{host}/") or lowered == host:
            return True
    return False


def normalize_short_url(url: str) -> str:
    """确保短链带 https:// 前缀，便于传给 aiohttp。"""
    stripped = (url or "").strip()
    if stripped.lower().startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped}"


def normalize_url(url: str) -> str:
    stripped = (url or "").strip().rstrip(".,;:!?，。；：！？）)」』\"'")
    if not stripped:
        return ""
    if stripped.lower().startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped}"


def extract_douyin_urls(text: str) -> list[str]:
    """从分享文案中提取抖音 URL（保序去重）。"""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for match in _URL_RE.findall(text):
        url = normalize_url(match)
        if not url or url in seen:
            continue
        host = (urlparse(url).hostname or "").lower()
        if not (_is_douyin_web_host(host) or is_short_url(url)):
            continue
        seen.add(url)
        found.append(url)
    return found


def parse_url_type(url: str) -> Optional[str]:
    """识别 URL 类型；单视频路径仅关心 short/video。"""
    if is_short_url(url):
        return "short"

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path

    if not _is_douyin_web_host(host):
        return None

    qs = parse_qs(parsed.query)
    modal_ids = qs.get("modal_id", [])
    if modal_ids and modal_ids[0].strip():
        return "video"

    if "/video/" in path:
        return "video"
    if "/note/" in path or "/gallery/" in path or "/slides/" in path:
        return "gallery"
    return None
