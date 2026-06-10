"""Tests for shared.bilibili.qrcode_login."""

from __future__ import annotations

import pytest

from shared.bilibili.qrcode_login import (
    BilibiliQrcodeError,
    _signed_tv_params,
    cookie_info_to_header,
)


def test_signed_tv_params_contains_sign() -> None:
    params = _signed_tv_params()
    assert params["appkey"]
    assert params["local_id"] == "0"
    assert isinstance(params["ts"], int)
    assert len(params["sign"]) == 32


def test_signed_tv_params_with_auth_code() -> None:
    params = _signed_tv_params(auth_code="test-auth-code")
    assert params["auth_code"] == "test-auth-code"
    assert len(params["sign"]) == 32


def test_cookie_info_to_header() -> None:
    header = cookie_info_to_header(
        {
            "cookies": [
                {"name": "SESSDATA", "value": "abc"},
                {"name": "bili_jct", "value": "xyz"},
            ]
        }
    )
    assert header == "SESSDATA=abc; bili_jct=xyz"


def test_cookie_info_to_header_missing_cookies_raises() -> None:
    with pytest.raises(BilibiliQrcodeError, match="Cookie"):
        cookie_info_to_header({"cookies": []})
