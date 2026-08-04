"""msToken generation (ported from douyin-downloader MsTokenManager)."""

from __future__ import annotations

import json
import random
import string
import time
import urllib.request
from http.cookies import SimpleCookie
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from urllib.parse import urlparse

from nonebot.log import logger

# Vendored from f2 conf (commit 019b3fb…); do not fetch remote YAML at runtime.
_VENDORED_MS_TOKEN_CONF = Path(__file__).with_name("f2_ms_token.json")
_ALLOWED_MS_TOKEN_HOSTS = frozenset(
    {
        "mssdk.bytedance.com",
        "mssdk.zijieapi.com",
    }
)
_REQUIRED_MS_TOKEN_KEYS = frozenset(
    {"url", "magic", "version", "dataType", "ulr", "strData"}
)


def _host_allowed(host: str, allowed: frozenset[str]) -> bool:
    normalized = (host or "").strip().lower().rstrip(".")
    if not normalized:
        return False
    return any(
        normalized == base or normalized.endswith("." + base) for base in allowed
    )


def is_allowed_ms_token_url(url: str) -> bool:
    """Return True when url is https to an allowlisted mssdk host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if parsed.username or parsed.password:
        return False
    return _host_allowed(parsed.hostname or "", _ALLOWED_MS_TOKEN_HOSTS)


class MsTokenManager:
    """Prefer real mssdk token; fall back to a random token."""

    _cached_conf: Optional[dict[str, Any]] = None
    _lock = Lock()

    def __init__(
        self,
        user_agent: str,
        conf_path: Optional[Path] = None,
        timeout_seconds: int = 15,
    ):
        self.user_agent = user_agent
        self.conf_path = Path(conf_path) if conf_path else _VENDORED_MS_TOKEN_CONF
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
        conf = self._load_ms_token_conf()
        if not conf:
            return None
        endpoint = str(conf.get("url") or "").strip()
        if not is_allowed_ms_token_url(endpoint):
            logger.warning("拒绝非白名单 msToken URL（host 校验失败）")
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
            endpoint,
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

    def _load_ms_token_conf(self) -> Optional[dict[str, Any]]:
        with self._lock:
            if self._cached_conf is not None:
                return self._cached_conf
        try:
            data = json.loads(self.conf_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                logger.warning("msToken 配置格式无效: {}", self.conf_path)
                return None
            if not _REQUIRED_MS_TOKEN_KEYS.issubset(data.keys()):
                logger.warning(
                    "msToken 配置不完整，缺少: {}",
                    sorted(_REQUIRED_MS_TOKEN_KEYS - set(data.keys())),
                )
                return None
            if not is_allowed_ms_token_url(str(data.get("url") or "")):
                logger.warning("msToken URL 未通过 host 白名单，忽略配置")
                return None
            with self._lock:
                self._cached_conf = data
            return data
        except Exception as exc:
            logger.warning("加载 msToken 配置失败: {}", exc)
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
