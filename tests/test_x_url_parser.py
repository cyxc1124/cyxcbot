"""Tests for X URL / tweet-id parsing and redirect host checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.x_api.url_parser import (
    extract_x_urls,
    is_blocked_redirect_host,
    parse_tweet_id_from_url,
    resolve_tco,
)


def test_parse_status_urls():
    assert (
        parse_tweet_id_from_url("https://x.com/elonmusk/status/1234567890123456789")
        == "1234567890123456789"
    )
    assert (
        parse_tweet_id_from_url(
            "https://twitter.com/elonmusk/status/1234567890123456789"
        )
        == "1234567890123456789"
    )
    assert (
        parse_tweet_id_from_url("https://x.com/i/web/status/9876543210") == "9876543210"
    )
    assert parse_tweet_id_from_url("https://x.com/i/status/111") == "111"
    assert parse_tweet_id_from_url("https://t.co/abc123") is None
    assert parse_tweet_id_from_url("https://example.com/status/1") is None


def test_parse_rejects_hostname_suffix_spoof():
    assert parse_tweet_id_from_url("https://notx.com/u/status/123") is None
    assert parse_tweet_id_from_url("https://foox.com/a/status/456") is None


def test_extract_x_urls_ignores_non_x():
    text = (
        "看这个 https://x.com/foo/status/42 还有 "
        "https://www.bilibili.com/video/BV1xx411c7mD "
        "以及 https://t.co/AbCdEfG"
    )
    urls = extract_x_urls(text)
    assert urls == [
        "https://x.com/foo/status/42",
        "https://t.co/AbCdEfG",
    ]


def test_extract_x_urls_rejects_embedded_hostname():
    text = "spoof https://notx.com/u/status/123 and https://x.com/a/status/9"
    assert extract_x_urls(text) == ["https://x.com/a/status/9"]


def test_extract_x_urls_dedupe_order():
    text = "https://x.com/a/status/1 https://x.com/a/status/1 https://twitter.com/b/status/2"
    assert extract_x_urls(text) == [
        "https://x.com/a/status/1",
        "https://twitter.com/b/status/2",
    ]


def test_blocked_redirect_hosts():
    assert is_blocked_redirect_host("127.0.0.1")
    assert is_blocked_redirect_host("10.0.0.1")
    assert is_blocked_redirect_host("192.168.1.1")
    assert is_blocked_redirect_host("localhost")
    assert is_blocked_redirect_host("169.254.169.254")
    assert not is_blocked_redirect_host("1.1.1.1")


@pytest.mark.asyncio
async def test_resolve_tco_rejects_private_redirect():
    session = MagicMock()

    class _Resp:
        status = 302
        headers = {"Location": "http://127.0.0.1:8080/secret"}
        url = "https://t.co/abc"

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=_Resp())
    cm.__aexit__ = AsyncMock(return_value=None)
    session.get = MagicMock(return_value=cm)

    assert await resolve_tco(session, "https://t.co/abc") is None


@pytest.mark.asyncio
async def test_resolve_tco_follows_to_x_status():
    session = MagicMock()

    class _Redirect:
        status = 302
        headers = {"Location": "https://x.com/foo/status/42"}
        url = "https://t.co/abc"

    class _Final:
        status = 200
        headers = {}
        url = "https://x.com/foo/status/42"

    first = MagicMock()
    first.__aenter__ = AsyncMock(return_value=_Redirect())
    first.__aexit__ = AsyncMock(return_value=None)
    second = MagicMock()
    second.__aenter__ = AsyncMock(return_value=_Final())
    second.__aexit__ = AsyncMock(return_value=None)
    session.get = MagicMock(side_effect=[first, second])

    assert (
        await resolve_tco(session, "https://t.co/abc") == "https://x.com/foo/status/42"
    )
