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
        key = (username or "").strip().lstrip("@").strip().lower()
        if not key:
            return None
        cached = self._user_cache.get(key)
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
            username=str(data.get("username") or key)
            .strip()
            .lstrip("@")
            .strip()
            .lower(),
            name=str(data.get("name") or ""),
        )
        self._user_cache[user.username.lower()] = user
        return user

    async def fetch_user_tweets(
        self,
        user_id: str,
        *,
        max_results: int = 5,
        since_id: str | None = None,
        username: str = "",
        name: str = "",
        max_pages: int = 20,
        paginate: bool = False,
    ) -> Optional[List[TweetItem]]:
        """Fetch recent tweets for a user id. Returns None on request failure.

        When ``since_id`` is set or ``paginate`` is true, pages are followed via
        ``pagination_token`` until exhausted. If the page cap is hit while more
        results remain, returns ``None`` so the cursor is not advanced past
        unseen tweets.
        """
        uid = str(user_id or "").strip()
        if not uid:
            return None
        if not self.bearer:
            logger.warning("X API: 未配置 Bearer Token，无法拉取推文")
            return None

        # since_id 增量或已初始化的零游标追赶都需要翻页，避免一次只拿最新 5 条漏帖
        use_pagination = bool(since_id) or paginate
        page_size = 100 if use_pagination else max_results
        page_limit = max(1, min(20, int(max_pages))) if use_pagination else 1

        handle = (username or "").strip().lstrip("@").strip()
        display_name = name or handle
        items: List[TweetItem] = []
        pagination_token: str | None = None

        for _ in range(page_limit):
            params = build_user_timeline_params(
                max_results=page_size,
                since_id=since_id,
                pagination_token=pagination_token,
            )
            payload = await self._get_user_timeline_page(uid, params)
            if payload is None:
                # 中途失败时丢弃已拉到的部分结果，避免游标被推到最新 ID 后永久漏帖
                return None

            media_by_key = _index_media(payload.get("includes"))
            page_rows = payload.get("data") or []
            for row in page_rows:
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                tweet_id = str(row["id"])
                media_urls = _media_urls_for_tweet(row, media_by_key)
                items.append(
                    TweetItem(
                        id=tweet_id,
                        text=str(row.get("text") or ""),
                        created_at=str(row.get("created_at") or ""),
                        username=handle,
                        name=display_name,
                        url=(
                            f"https://x.com/{handle}/status/{tweet_id}"
                            if handle
                            else f"https://x.com/i/status/{tweet_id}"
                        ),
                        media_urls=media_urls,
                    )
                )

            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            next_token = str(meta.get("next_token") or "").strip()
            if not next_token or not page_rows:
                break
            pagination_token = next_token
        else:
            # 触顶 page_limit 且仍有下一页：视为不完整，避免推进游标漏帖
            if use_pagination:
                logger.warning(
                    "X API 推文翻页未完成: user_id={} pages={}，下次重试",
                    uid,
                    page_limit,
                )
                return None

        items.sort(key=lambda t: tweet_id_as_int(t.id), reverse=True)
        return items

    async def _get_user_timeline_page(
        self, user_id: str, params: dict[str, str]
    ) -> Optional[dict]:
        url = f"{_API_BASE}/users/{user_id}/tweets"
        try:
            async with self.session.get(
                url, params=params, **self._request_kwargs()
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "X API 拉取推文失败: user_id={} HTTP {}",
                        user_id,
                        response.status,
                    )
                    return None
                payload = await response.json()
        except Exception:
            logger.opt(exception=True).error("X API 拉取推文异常: user_id={}", user_id)
            return None
        return payload if isinstance(payload, dict) else {}

    async def get_tweet_by_id(self, tweet_id: str) -> Optional[TweetItem]:
        """Fetch a single tweet by ID with author + media expansions."""
        tid = str(tweet_id or "").strip()
        if not tid:
            return None
        if not self.bearer:
            logger.warning("X API: 未配置 Bearer Token，无法拉取推文")
            return None

        url = f"{_API_BASE}/tweets/{tid}"
        params = {
            "tweet.fields": "created_at,text,attachments,author_id",
            "expansions": "attachments.media_keys,author_id",
            "media.fields": "url,preview_image_url,type",
            "user.fields": "name,username",
        }
        try:
            async with self.session.get(
                url, params=params, **self._request_kwargs()
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "X API 拉取单条推文失败: tweet_id={} HTTP {}",
                        tid,
                        response.status,
                    )
                    return None
                payload = await response.json()
        except Exception:
            logger.opt(exception=True).error("X API 拉取单条推文异常: tweet_id={}", tid)
            return None

        if not isinstance(payload, dict):
            return None
        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("id"):
            return None

        includes = (
            payload.get("includes") if isinstance(payload.get("includes"), dict) else {}
        )
        media_by_key = _index_media(includes)
        users_by_id = _index_users(includes)
        author_id = str(data.get("author_id") or "").strip()
        author = users_by_id.get(author_id) or {}
        handle = str(author.get("username") or "").strip().lstrip("@").strip().lower()
        display_name = str(author.get("name") or handle)
        tweet_id_str = str(data["id"])
        return TweetItem(
            id=tweet_id_str,
            text=str(data.get("text") or ""),
            created_at=str(data.get("created_at") or ""),
            username=handle,
            name=display_name,
            url=(
                f"https://x.com/{handle}/status/{tweet_id_str}"
                if handle
                else f"https://x.com/i/status/{tweet_id_str}"
            ),
            media_urls=_media_urls_for_tweet(data, media_by_key),
        )


def build_user_timeline_params(
    *,
    max_results: int = 5,
    since_id: str | None = None,
    pagination_token: str | None = None,
) -> dict[str, str]:
    """Build GET /2/users/:id/tweets query params (testable without HTTP)."""
    clamped = max(5, min(100, int(max_results)))
    params: dict[str, str] = {
        "max_results": str(clamped),
        "exclude": "retweets,replies",
        "tweet.fields": "created_at,text,attachments",
        "expansions": "attachments.media_keys",
        "media.fields": "url,preview_image_url,type",
    }
    sid = str(since_id or "").strip()
    if sid and sid != "0" and tweet_id_as_int(sid) > 0:
        params["since_id"] = sid
    token = str(pagination_token or "").strip()
    if token:
        params["pagination_token"] = token
    return params


def _index_media(includes: Any) -> Dict[str, dict]:
    if not isinstance(includes, dict):
        return {}
    media_list = includes.get("media") or []
    result: Dict[str, dict] = {}
    for item in media_list:
        if isinstance(item, dict) and item.get("media_key"):
            result[str(item["media_key"])] = item
    return result


def _index_users(includes: Any) -> Dict[str, dict]:
    if not isinstance(includes, dict):
        return {}
    users = includes.get("users") or []
    result: Dict[str, dict] = {}
    for item in users:
        if isinstance(item, dict) and item.get("id"):
            result[str(item["id"])] = item
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
