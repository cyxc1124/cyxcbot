"""msToken remote conf must not drive arbitrary SSRF POSTs."""

from __future__ import annotations

from utils.douyin_api.ms_token import is_allowed_ms_token_url


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


def test_f2_conf_url_is_commit_pinned() -> None:
    from utils.douyin_api.ms_token import MsTokenManager

    assert "/main/" not in MsTokenManager.F2_CONF_URL
    assert "019b3fb61c6c62d091eb9000738a7a5b177de3a2" in MsTokenManager.F2_CONF_URL
