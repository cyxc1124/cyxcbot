"""msToken conf must not drive arbitrary SSRF POSTs."""

from __future__ import annotations

import json
from pathlib import Path

from utils.douyin_api.ms_token import (
    _VENDORED_MS_TOKEN_CONF,
    is_allowed_ms_token_url,
)


def test_allows_https_mssdk_hosts() -> None:
    assert is_allowed_ms_token_url(
        "https://mssdk.bytedance.com/web/r/token?ms_appid=6383"
    )
    assert is_allowed_ms_token_url("https://mssdk.zijieapi.com/web/r/token")


def test_rejects_non_https_or_unlisted_hosts() -> None:
    assert not is_allowed_ms_token_url("http://mssdk.bytedance.com/web/r/token")
    assert not is_allowed_ms_token_url("https://evil.example/ssrf")
    assert not is_allowed_ms_token_url("https://127.0.0.1/token")
    assert not is_allowed_ms_token_url(
        "https://user:pass@mssdk.bytedance.com/web/r/token"
    )
    assert not is_allowed_ms_token_url("")


def test_vendored_ms_token_conf_is_local_and_allowlisted() -> None:
    assert _VENDORED_MS_TOKEN_CONF.is_file()
    data = json.loads(_VENDORED_MS_TOKEN_CONF.read_text(encoding="utf-8"))
    required = {"url", "magic", "version", "dataType", "ulr", "strData"}
    assert required.issubset(data)
    assert is_allowed_ms_token_url(str(data["url"]))
    # no runtime fetch of f2 main/raw
    text = Path("utils/douyin_api/ms_token.py").read_text(encoding="utf-8")
    assert "raw.githubusercontent.com" not in text
    assert "Johnserf-Seed/f2" not in text
