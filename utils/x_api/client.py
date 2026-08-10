"""X (Twitter) API v2 client."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import aiohttp
from nonebot.log import logger

from shared.config.proxy import ProxyConfig

from .models import TweetItem, XUser, tweet_id_as_int

_API_BASE = "https://api.x.com/2"


def create_session(proxy: ProxyConfig | None = None) -> aiohttp.ClientSession:
    """Create an aiohttp session; SOCKS5 uses ProxyConnector, else plain TCP."""
    if proxy is not None and proxy.is_configured and proxy.scheme == "socks5":
        from aiohttp_socks import ProxyConnector

        url = proxy.to_url()
        if url:
            return aiohttp.ClientSession(connector=ProxyConnector.from_url(url))
    return aiohttp.ClientSession()


class XApiClient:
    """Minimal X API v2 client for user lookup and recent tweets."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        bearer: str,
        proxy_url: Optional[str] = None,
    ) -> None:
        self.session = session
        self.bearer = (bearer or "").strip()
        # http/https 代理走 per-request；socks5 已在 connector 层处理
        self.proxy_url = proxy_url
        self._user_cache: Dict[str, XUser] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer}",
            "User-Agent": "cyxcbot-x-monitor/1.0",
        }

    def _request_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"headers": self._headers(), "timeout": 30}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return kwargs

    async def get_user_by_username(self, username: str) -> Optional[XUser]:
        """Resolve username (without @) to XUser."""
        key = (username or "").lstrip("@").strip()
        if not key:
            return None
        cached = self._user_cache.get(key.lower())
        if cached:
            return cached
        if not self.bearer:
            logger.warning("X API: 未配置 Bearer Token，无法查询用户")
            return None

        url = f"{_API_BASE}/users/by/username/{key}"
        params = {"user.fields": "name,username"}
        try:
            async with self.session.get(
                url, params=params, **self._request_kwargs()
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "X API 查询用户失败: username={} HTTP {}",
                        key,
                        response.status,
                    )
                    return None
                payload = await response.json()
        except Exception:
            logger.opt(exception=True).error("X API 查询用户异常: username={}", key)
            return None

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not data.get("id"):
            logger.debug("X API 未找到用户: {}", key)
            return None

        user = XUser(
            id=str(data["id"]),
            username=str(data.get("username") or key).lstrip("@"),
            name=str(data.get("name") or ""),
        )
        self._user_cache[user.username.lower()] = user
        return user

    async def fetch_user_tweets(
        self,
        user_id: str,
        *,
        max_results: int = 5,
        username: str = "",
        name: str = "",
    ) -> Optional[List[TweetItem]]:
        """Fetch recent tweets for a user id. Returns None on request failure."""
        uid = str(user_id or "").strip()
        if not uid:
            return None
        if not self.bearer:
            logger.warning("X API: 未配置 Bearer Token，无法拉取推文")
            return None

        clamped = max(5, min(100, int(max_results)))
        url = f"{_API_BASE}/users/{uid}/tweets"
        params = {
            "max_results": str(clamped),
            "exclude": "retweets,replies",
            "tweet.fields": "created_at,text,attachments",
            "expansions": "attachments.media_keys",
            "media.fields": "url,preview_image_url,type",
        }
        try:
            async with self.session.get(
                url, params=params, **self._request_kwargs()
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "X API 拉取推文失败: user_id={} HTTP {}",
                        uid,
                        response.status,
                    )
                    return None
                payload = await response.json()
        except Exception:
            logger.opt(exception=True).error("X API 拉取推文异常: user_id={}", uid)
            return None

        if not isinstance(payload, dict):
            return []

        media_by_key = _index_media(payload.get("includes"))
        items: List[TweetItem] = []
        for row in payload.get("data") or []:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            tweet_id = str(row["id"])
            handle = (username or "").lstrip("@")
            media_urls = _media_urls_for_tweet(row, media_by_key)
            items.append(
                TweetItem(
                    id=tweet_id,
                    text=str(row.get("text") or ""),
                    created_at=str(row.get("created_at") or ""),
                    username=handle,
                    name=name or handle,
                    url=(
                        f"https://x.com/{handle}/status/{tweet_id}"
                        if handle
                        else f"https://x.com/i/status/{tweet_id}"
                    ),
                    media_urls=media_urls,
                )
            )

        items.sort(key=lambda t: tweet_id_as_int(t.id), reverse=True)
        return items


def _index_media(includes: Any) -> Dict[str, dict]:
    if not isinstance(includes, dict):
        return {}
    media_list = includes.get("media") or []
    result: Dict[str, dict] = {}
    for item in media_list:
        if isinstance(item, dict) and item.get("media_key"):
            result[str(item["media_key"])] = item
    return result


def _media_urls_for_tweet(tweet: dict, media_by_key: Dict[str, dict]) -> List[str]:
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
