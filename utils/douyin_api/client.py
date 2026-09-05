"""Douyin web API client (single-video subset from douyin-downloader)."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp
from nonebot.log import logger
from yarl import URL

from .cookie_utils import (
    cookie_header,
    cookies_from_http_response,
    cookies_from_morsels,
    sanitize_cookies,
)
from .ms_token import MsTokenManager
from .xbogus import XBogus

try:
    from .abogus import ABogus, BrowserFingerprintGenerator
except Exception:  # pragma: no cover - optional dependency
    ABogus = None
    BrowserFingerprintGenerator = None

_LOGIN_REQUIRED_STATUS_CODES = {2483}

# 与 _default_query 里 Windows / Chrome 139 指纹对齐；随机 Mac UA 会和 query 打架。
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)

# 403 是抖音 WAF 拒这次签名，不是登录失败；换 a_bogus 再试经常能过。
_RETRYABLE_HTTP_STATUSES = frozenset({403, 429})


def _should_retry_http_status(status: int) -> bool:
    return status >= 500 or status in _RETRYABLE_HTTP_STATUSES


class LoginRequiredError(Exception):
    def __init__(self, status_code: int, status_msg: str, path: str):
        self.status_code = status_code
        self.status_msg = status_msg
        self.path = path
        super().__init__(
            f"login required (status_code={status_code}) at {path}: {status_msg}"
        )


def safe_log_url(value: object) -> str:
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
        netloc = parsed.netloc.rsplit("@", 1)[-1]
        clean = urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
        query_keys = sorted(
            {key for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}
        )
    except TypeError, ValueError:
        return text.split("?", 1)[0].split("#", 1)[0]
    if not query_keys:
        return clean
    return f"{clean}?[query_keys={','.join(query_keys)}]"


def _is_login_required(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    code = data.get("status_code")
    msg = str(data.get("status_msg") or "")
    return (
        code in _LOGIN_REQUIRED_STATUS_CODES or "请先登录" in msg or "用户未登录" in msg
    )


def _safe_error_text(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    text = re.sub(r"(https?://[^?\s]+)\?\S+", r"\1?[redacted-query]", text)
    return text[:500]


class DouyinAPIClient:
    BASE_URL = "https://www.douyin.com"
    _DETAIL_AID_CANDIDATES = ("6383", "1128")

    def __init__(self, cookies: dict[str, str], proxy: Optional[str] = None):
        self.cookies = sanitize_cookies(cookies or {})
        self.proxy = str(proxy or "").strip()
        self._session: Optional[aiohttp.ClientSession] = None
        selected_ua = _USER_AGENT
        self.headers = {
            "User-Agent": selected_ua,
            "Referer": "https://www.douyin.com/?recommend=1",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self._signer = XBogus(self.headers["User-Agent"])
        self._ms_token_manager = MsTokenManager(user_agent=self.headers["User-Agent"])
        self._ms_token = (self.cookies.get("msToken") or "").strip()
        self._abogus_enabled = (
            ABogus is not None and BrowserFingerprintGenerator is not None
        )

    async def __aenter__(self) -> DouyinAPIClient:
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def _seed_cookie_jar(self) -> aiohttp.CookieJar:
        jar = aiohttp.CookieJar()
        if self.cookies:
            jar.update_cookies(self.cookies, response_url=URL(f"{self.BASE_URL}/"))
        return jar

    def _request_cookie_header(self, url: str | None = None) -> str:
        merged = dict(self.cookies)
        jar = getattr(self._session, "cookie_jar", None) if self._session else None
        if jar is not None:
            merged.update(
                cookies_from_morsels(
                    jar.filter_cookies(URL(url or f"{self.BASE_URL}/"))
                )
            )
        return cookie_header(merged)

    def _merge_response_cookies(self, response: object) -> None:
        incoming = cookies_from_http_response(response)
        if not incoming:
            return
        self.cookies.update(incoming)
        if incoming.get("msToken"):
            self._ms_token = incoming["msToken"]
        jar = getattr(self._session, "cookie_jar", None) if self._session else None
        if jar is None:
            return
        raw_url = str(getattr(response, "url", "") or "")
        jar.update_cookies(incoming, response_url=URL(raw_url or f"{self.BASE_URL}/"))

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                cookie_jar=self._seed_cookie_jar(),
                timeout=aiohttp.ClientTimeout(total=30),
                raise_for_status=False,
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_session(self) -> aiohttp.ClientSession:
        await self._ensure_session()
        if self._session is None:
            raise RuntimeError("Failed to create aiohttp session")
        return self._session

    async def _ensure_ms_token(self) -> str:
        if self._ms_token:
            return self._ms_token
        token = await asyncio.to_thread(
            self._ms_token_manager.ensure_ms_token,
            self.cookies,
        )
        self._ms_token = token.strip()
        if self._ms_token:
            self.cookies["msToken"] = self._ms_token
            jar = getattr(self._session, "cookie_jar", None) if self._session else None
            if jar is not None:
                jar.update_cookies(
                    {"msToken": self._ms_token},
                    response_url=URL(f"{self.BASE_URL}/"),
                )
        return self._ms_token

    async def _default_query(self) -> dict[str, Any]:
        ms_token = await self._ensure_ms_token()
        return {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "update_version_code": "170400",
            "pc_client_type": "1",
            "pc_libra_divert": "Windows",
            "version_code": "290100",
            "version_name": "29.1.0",
            "cookie_enabled": "true",
            "screen_width": "1536",
            "screen_height": "864",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "139.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "139.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": "16",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "200",
            "support_h265": "1",
            "support_dash": "1",
            "uifid": "",
            "msToken": ms_token,
        }

    def sign_url(self, url: str) -> tuple[str, str]:
        signed_url, _xbogus, ua = self._signer.build(url)
        return signed_url, ua

    def build_signed_path(
        self,
        path: str,
        params: dict[str, Any],
        *,
        base_url: Optional[str] = None,
        request_data: Optional[dict[str, Any]] = None,
    ) -> tuple[str, str]:
        query = urlencode(params)
        endpoint = f"{(base_url or self.BASE_URL).rstrip('/')}{path}"
        ab_signed = self._build_abogus_url(endpoint, query, request_data=request_data)
        if ab_signed:
            return ab_signed
        return self.sign_url(f"{endpoint}?{query}")

    def _build_abogus_url(
        self,
        base_url: str,
        query: str,
        *,
        request_data: Optional[dict[str, Any]] = None,
    ) -> Optional[tuple[str, str]]:
        if not self._abogus_enabled:
            return None
        try:
            browser_fp = BrowserFingerprintGenerator.generate_fingerprint("Chrome")
            signer = ABogus(fp=browser_fp, user_agent=self.headers["User-Agent"])
            body = urlencode(request_data or {})
            params_with_ab, _ab, ua, _body = signer.generate_abogus(query, body)
            return f"{base_url}?{params_with_ab}", ua
        except Exception as exc:
            logger.warning("生成 a_bogus 失败，回退 X-Bogus: {}", exc)
            return None

    async def _request_json(
        self,
        path: str,
        params: dict[str, Any],
        *,
        suppress_error: bool = False,
        max_retries: int = 3,
        base_url: Optional[str] = None,
        request_headers: Optional[dict[str, str]] = None,
        method: str = "GET",
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        await self._ensure_session()
        method = method.upper()
        if method not in {"GET", "POST"}:
            raise ValueError(f"unsupported request method: {method}")
        delays = [1, 2, 5]
        last_exc: Optional[Exception] = None
        assert self._session is not None

        for attempt in range(max_retries):
            signing_kwargs: dict[str, Any] = {}
            if base_url:
                signing_kwargs["base_url"] = base_url
            if method == "POST":
                signing_kwargs["request_data"] = data
            signed_url, ua = self.build_signed_path(path, params, **signing_kwargs)
            headers = {**self.headers, **(request_headers or {}), "User-Agent": ua}
            cookie = self._request_cookie_header(signed_url)
            if cookie:
                headers["Cookie"] = cookie
            request = self._session.post if method == "POST" else self._session.get
            request_kwargs: dict[str, Any] = {
                "headers": headers,
                "proxy": self.proxy or None,
            }
            if method == "POST":
                request_kwargs["data"] = data or {}
            try:
                async with request(signed_url, **request_kwargs) as response:
                    self._merge_response_cookies(response)
                    if response.status == 200:
                        body = await response.read()
                        if not body:
                            last_exc = RuntimeError(
                                f"Empty 200 response for {path} (anti-bot)"
                            )
                            logger.warning(
                                "抖音 API 空 200 响应 path={} attempt={}/{}，疑似反爬",
                                path,
                                attempt + 1,
                                max_retries,
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(
                                    delays[min(attempt, len(delays) - 1)]
                                )
                            continue
                        try:
                            parsed = await response.json(content_type=None)
                        except Exception:
                            try:
                                parsed = json.loads(body)
                            except Exception:
                                logger.warning(
                                    "抖音 API 非 JSON 响应 path={} length={}",
                                    path,
                                    len(body),
                                )
                                return {}
                        result = parsed if isinstance(parsed, dict) else {}
                        if _is_login_required(result):
                            raise LoginRequiredError(
                                int(result.get("status_code") or 0),
                                str(result.get("status_msg") or ""),
                                path,
                            )
                        return result
                    if not _should_retry_http_status(response.status):
                        log_fn = logger.info if suppress_error else logger.error
                        log_fn(
                            "抖音 API HTTP 失败 path={} status={} attempt={}/{}",
                            path,
                            response.status,
                            attempt + 1,
                            max_retries,
                        )
                        return {}
                    last_exc = RuntimeError(f"HTTP {response.status} for {path}")
                    logger.warning(
                        "抖音 API 可重试失败 path={} status={} attempt={}/{}",
                        path,
                        response.status,
                        attempt + 1,
                        max_retries,
                    )
            except LoginRequiredError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "抖音 API 请求异常 path={} attempt={}/{} error={}",
                    path,
                    attempt + 1,
                    max_retries,
                    _safe_error_text(exc),
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])

        log_fn = logger.info if suppress_error else logger.error
        log_fn(
            "抖音 API 重试耗尽 path={} error={}",
            path,
            _safe_error_text(last_exc) if last_exc else "-",
        )
        return {}

    async def get_video_detail(
        self, aweme_id: str, *, suppress_error: bool = False
    ) -> Optional[dict[str, Any]]:
        for aid in self._DETAIL_AID_CANDIDATES:
            params = await self._default_query()
            params.update({"aweme_id": aweme_id, "aid": aid})
            data = await self._request_json(
                "/aweme/v1/web/aweme/detail/",
                params,
                suppress_error=(
                    suppress_error or aid != self._DETAIL_AID_CANDIDATES[-1]
                ),
            )
            if not data:
                continue
            detail = data.get("aweme_detail")
            if detail:
                return detail
            filter_info = data.get("filter_detail")
            if isinstance(filter_info, dict) and filter_info.get("filter_reason"):
                logger.info(
                    "作品 {} 被 aid={} 过滤 (reason={})，重试",
                    aweme_id,
                    aid,
                    filter_info["filter_reason"],
                )
                continue
            break
        return None

    async def resolve_short_url(
        self, short_url: str, *, timeout_seconds: float = 10.0
    ) -> Optional[str]:
        try:
            await self._ensure_session()
            assert self._session is not None
            headers: dict[str, str] = {}
            cookie = self._request_cookie_header(short_url)
            if cookie:
                headers["Cookie"] = cookie
            async with self._session.get(
                short_url,
                allow_redirects=True,
                headers=headers or None,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                proxy=self.proxy or None,
            ) as response:
                self._merge_response_cookies(response)
                final_url = str(response.url)
                if response.status >= 400:
                    logger.warning(
                        "短链解析 HTTP {}：{} -> {}",
                        response.status,
                        safe_log_url(short_url),
                        safe_log_url(final_url),
                    )
                    return None
                return final_url
        except TimeoutError:
            logger.error(
                "短链解析超时 {:.1f}s: {}",
                timeout_seconds,
                safe_log_url(short_url),
            )
            return None
        except Exception as exc:
            logger.error(
                "短链解析失败: {} error={}",
                safe_log_url(short_url),
                exc,
            )
            return None
