"""Unit tests for Douyin QR login helpers (no Playwright / network)."""

import pytest

from shared.douyin.qrcode_login import (
    QR_SELECTORS,
    DouyinQrcodeError,
    cookies_to_header,
    has_valid_login_cookie,
    is_logged_in_url,
    refresh_qrcode_login,
)


def test_qr_selectors_prefer_live_hashed_container():
    # Live panel: .XI37I0dP > img.RhjdbXj8[aria-label=二维码]
    assert QR_SELECTORS[0] == ".XI37I0dP img"
    assert "img.RhjdbXj8" in QR_SELECTORS
    assert ".XI37I0dP" in QR_SELECTORS
    assert any("二维码" in s for s in QR_SELECTORS)


@pytest.mark.asyncio
async def test_refresh_requires_existing_session():
    with pytest.raises(DouyinQrcodeError, match="缺少|不存在|过期"):
        await refresh_qrcode_login("")
    with pytest.raises(DouyinQrcodeError, match="不存在|过期"):
        await refresh_qrcode_login("no-such-session")


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
