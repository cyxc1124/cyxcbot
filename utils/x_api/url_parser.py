"""Extract tweet IDs from X / Twitter / t.co URLs."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

import aiohttp

STATUS_RE = re.compile(
    r"(?:https?://)?(?:(?:www\.|mobile\.)?(?:x|twitter)\.com)/"
    r"(?:[^/\s?#]+/status|i/web/status|i/status)/(\d+)",
    re.IGNORECASE,
)

TCO_RE = re.compile(
    r"(?:https?://)?t\.co/[A-Za-z0-9]+/?",
    re.IGNORECASE,
)

_X_URL_RE = re.compile(
    r"(?:https?://)?(?:(?:(?:www\.|mobile\.)?(?:x|twitter)\.com)/[^\s<>\"']+|t\.co/[A-Za-z0-9]+/?)",
    re.IGNORECASE,
)


def _normalize_url(url: str) -> str:
    stripped = (url or "").strip().rstrip(".,;:!?，。；：！？）)」』\"'")
    if not stripped:
        return ""
    if stripped.lower().startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped}"


def extract_x_urls(text: str) -> list[str]:
    """从文案中提取 X / Twitter / t.co URL（保序去重）。"""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for match in _X_URL_RE.findall(text):
        url = _normalize_url(match)
        if not url or url in seen:
            continue
        host = (urlparse(url).hostname or "").lower()
        if host in {"x.com", "twitter.com", "t.co"} or host.endswith(
            (".x.com", ".twitter.com")
        ):
            seen.add(url)
            found.append(url)
    return found


def parse_tweet_id_from_url(url: str) -> Optional[str]:
    """从 status URL 解析推文 ID；非 status 链接返回 None。"""
    if not url:
        return None
    match = STATUS_RE.search(_normalize_url(url))
    if not match:
        return None
    return match.group(1)


async def resolve_tco(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Follow t.co redirects; return final URL or None."""
    target = _normalize_url(url)
    if not target:
        return None
    try:
        async with session.get(
            target,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            return str(response.url)
    except Exception:
        return None


async def extract_x_tweet_ids(text: str, session: aiohttp.ClientSession) -> list[str]:
    """从文案提取推文 ID（保序去重；t.co 会跟随重定向）。"""
    ids: list[str] = []
    seen: set[str] = set()
    for url in extract_x_urls(text):
        tweet_id = parse_tweet_id_from_url(url)
        if not tweet_id and TCO_RE.search(url):
            resolved = await resolve_tco(session, url)
            if resolved:
                tweet_id = parse_tweet_id_from_url(resolved)
        if not tweet_id or tweet_id in seen:
            continue
        seen.add(tweet_id)
        ids.append(tweet_id)
    return ids
