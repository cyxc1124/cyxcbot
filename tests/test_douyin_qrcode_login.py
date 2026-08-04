"""Unit tests for Douyin QR login helpers (no Playwright / network)."""

from shared.douyin.qrcode_login import (
    cookies_to_header,
    has_valid_login_cookie,
    is_logged_in_url,
)


def test_cookies_to_header_and_sessionid_check():
    cookies = [
        {"name": "ttwid", "value": "a"},
        {"name": "sessionid", "value": "sid123"},
        {"name": "empty", "value": None},
    ]
    header = cookies_to_header(cookies)
    assert "ttwid=a" in header
    assert "sessionid=sid123" in header
    assert "empty=" not in header
    assert has_valid_login_cookie(cookies)
    assert not has_valid_login_cookie([{"name": "ttwid", "value": "a"}])


def test_is_logged_in_url():
    assert is_logged_in_url("https://www.douyin.com/")
    assert is_logged_in_url("https://www.douyin.com/user/xxx")
    assert not is_logged_in_url("https://www.douyin.com/passport/login")
    assert not is_logged_in_url("https://example.com/")
