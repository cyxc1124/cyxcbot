"""Tests for X URL / tweet-id parsing."""

from __future__ import annotations

from utils.x_api.url_parser import extract_x_urls, parse_tweet_id_from_url


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


def test_extract_x_urls_dedupe_order():
    text = "https://x.com/a/status/1 https://x.com/a/status/1 https://twitter.com/b/status/2"
    assert extract_x_urls(text) == [
        "https://x.com/a/status/1",
        "https://twitter.com/b/status/2",
    ]
