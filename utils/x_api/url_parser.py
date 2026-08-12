"""Extract tweet IDs from X / Twitter / t.co URLs."""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiohttp

# 必须以 URL 边界开头，避免 notx.com 被当成 x.com。
_URL_BOUNDARY = r"(?<![A-Za-z0-9.-])"

STATUS_RE = re.compile(
    _URL_BOUNDARY
    + r"(?:https?://)?(?:(?:www\.|mobile\.)?(?:x|twitter)\.com)/"
    + r"(?:[^/\s?#]+/status|i/web/status|i/status)/(\d+)",
    re.IGNORECASE,
)

TCO_RE = re.compile(
    _URL_BOUNDARY + r"(?:https?://)?t\.co/[A-Za-z0-9]+/?",
    re.IGNORECASE,
)

_X_URL_RE = re.compile(
    _URL_BOUNDARY
    + r"(?:https?://)?(?:(?:(?:www\.|mobile\.)?(?:x|twitter)\.com)/[^\s<>\"']+"
    + r"|t\.co/[A-Za-z0-9]+/?)",
    re.IGNORECASE,
)

_STATUS_PATH_RE = re.compile(
    r"^/(?:[^/]+/status|i/web/status|i/status)/(\d+)(?:/|$|\?|#)",
    re.IGNORECASE,
)

_X_HOSTS = frozenset({"x.com", "twitter.com", "t.co"})
_MAX_TCO_HOPS = 5


def _normalize_url(url: str) -> str:
    stripped = (url or "").strip().rstrip(".,;:!?，。；：！？）)」』\"'")
    if not stripped:
        return ""
    if stripped.lower().startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped}"


def _is_x_hostname(host: str | None) -> bool:
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False
    if h in _X_HOSTS:
        return True
    return h.endswith((".x.com", ".twitter.com"))


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or (ip.version == 4 and ip == ipaddress.IPv4Address("169.254.169.254"))
    )


def is_blocked_redirect_host(hostname: str | None) -> bool:
    """Reject localhost / private / link-local / metadata targets (SSRF)."""
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        return True
    # 目标本就是 X 系域名时不做 DNS 解析（避免沙箱/离线误杀，且不扩大 SSRF 面）。
    if _is_x_hostname(host):
        return False
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return True
    if host in {"metadata.google.internal", "metadata"}:
        return True
    try:
        return _is_blocked_ip(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        for info in socket.getaddrinfo(host, None):
            addr = info[4][0]
            try:
                if _is_blocked_ip(ipaddress.ip_address(addr)):
                    return True
            except ValueError:
                continue
    except OSError:
        return True
    return False


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
        if not _is_x_hostname(host):
            continue
        seen.add(url)
        found.append(url)
    return found


def parse_tweet_id_from_url(url: str) -> Optional[str]:
    """从 status URL 解析推文 ID；非 X status 链接返回 None。"""
    if not url:
        return None
    normalized = _normalize_url(url)
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if not _is_x_hostname(parsed.hostname):
        return None
    if (parsed.hostname or "").lower().rstrip(".") == "t.co":
        return None
    match = _STATUS_PATH_RE.match(parsed.path or "")
    if not match:
        return None
    return match.group(1)


async def resolve_tco(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Follow t.co redirects hop-by-hop; reject non-public destinations."""
    current = _normalize_url(url)
    if not current:
        return None
    parsed = urlparse(current)
    if (parsed.hostname or "").lower().rstrip(".") != "t.co":
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if is_blocked_redirect_host(parsed.hostname):
        return None

    try:
        for _ in range(_MAX_TCO_HOPS):
            host = urlparse(current).hostname
            if is_blocked_redirect_host(host):
                return None
            async with session.get(
                current,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = (response.headers.get("Location") or "").strip()
                    if not location:
                        return None
                    nxt = _normalize_url(urljoin(str(response.url), location))
                    nxt_parsed = urlparse(nxt)
                    if nxt_parsed.scheme not in {"http", "https"}:
                        return None
                    if is_blocked_redirect_host(nxt_parsed.hostname):
                        return None
                    current = nxt
                    continue
                final = str(response.url)
                if is_blocked_redirect_host(urlparse(final).hostname):
                    return None
                return final
    except Exception:
        return None
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
