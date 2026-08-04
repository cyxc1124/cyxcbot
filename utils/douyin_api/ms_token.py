"""msToken generation (ported from douyin-downloader MsTokenManager)."""

from __future__ import annotations

import json
import random
import string
import time
import urllib.request
from http.cookies import SimpleCookie
from threading import Lock
from typing import Any, Optional

import yaml
from nonebot.log import logger


class MsTokenManager:
    """Prefer real mssdk token; fall back to a random token."""

    F2_CONF_URL = (
        "https://raw.githubusercontent.com/Johnserf-Seed/f2/main/f2/conf/conf.yaml"
    )
    _cached_conf: Optional[dict[str, Any]] = None
    _cached_at: float = 0
    _cache_ttl_seconds: int = 3600
    _lock = Lock()

    def __init__(
        self,
        user_agent: str,
        conf_url: Optional[str] = None,
        timeout_seconds: int = 15,
    ):
        self.user_agent = user_agent
        self.conf_url = conf_url or self.F2_CONF_URL
        self.timeout_seconds = timeout_seconds

    @classmethod
    def _is_valid_ms_token(cls, token: Optional[str]) -> bool:
        if not token or not isinstance(token, str):
            return False
        return len(token.strip()) in (164, 184)

    @classmethod
    def gen_false_ms_token(cls) -> str:
        token = (
            "".join(
                random.choice(string.ascii_letters + string.digits) for _ in range(182)
            )
            + "=="
        )
        logger.debug("已生成回退 msToken")
        return token

    def ensure_ms_token(self, cookies: dict[str, str]) -> str:
        current = (cookies or {}).get("msToken", "").strip()
        if current:
            return current
        real = self.gen_real_ms_token()
        if real:
            return real
        return self.gen_false_ms_token()

    def gen_real_ms_token(self) -> Optional[str]:
        conf = self._load_f2_ms_token_conf()
        if not conf:
            return None
        payload = {
            "magic": conf["magic"],
            "version": conf["version"],
            "dataType": conf["dataType"],
            "strData": conf["strData"],
            "ulr": conf["ulr"],
            "tspFromClient": int(time.time() * 1000),
        }
        request = urllib.request.Request(
            conf["url"],
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                token = self._extract_ms_token_from_headers(resp.headers)
            if self._is_valid_ms_token(token):
                logger.debug("已通过 mssdk 生成真实 msToken")
                return token
            if token:
                logger.warning("生成的 msToken 长度异常: {}", len(token.strip()))
            return None
        except Exception as exc:
            logger.warning("生成真实 msToken 失败: {}", exc)
            return None

    def _load_f2_ms_token_conf(self) -> Optional[dict[str, Any]]:
        now = time.time()
        with self._lock:
            if self._cached_conf and (now - self._cached_at) < self._cache_ttl_seconds:
                return self._cached_conf
        try:
            with urllib.request.urlopen(
                self.conf_url, timeout=self.timeout_seconds
            ) as resp:
                raw = resp.read().decode("utf-8")
            data = yaml.safe_load(raw) or {}
            ms_conf = data.get("f2", {}).get("douyin", {}).get("msToken", {})
            required = {"url", "magic", "version", "dataType", "ulr", "strData"}
            if not required.issubset(ms_conf.keys()):
                logger.warning(
                    "F2 msToken 配置不完整，缺少: {}",
                    sorted(required - set(ms_conf.keys())),
                )
                return None
            with self._lock:
                self._cached_conf = ms_conf
                self._cached_at = now
            return ms_conf
        except Exception as exc:
            logger.warning("加载 F2 msToken 配置失败: {}", exc)
            return None

    @staticmethod
    def _extract_ms_token_from_headers(headers: Any) -> Optional[str]:
        set_cookies = (
            headers.get_all("Set-Cookie") if hasattr(headers, "get_all") else []
        )
        for header in set_cookies or []:
            cookie = SimpleCookie()
            cookie.load(header)
            morsel = cookie.get("msToken")
            if morsel and morsel.value:
                return morsel.value.strip()
        return None
