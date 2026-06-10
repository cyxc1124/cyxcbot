"""Tests for utils.bilibili_api.wbi."""

from __future__ import annotations

from utils.bilibili_api.wbi import (
    build_signed_query,
    encode_value,
    extract_key,
    make_key,
)


def test_extract_key() -> None:
    assert extract_key("https://i0.hdslb.com/bfs/wbi/abc123.png") == "abc123"


def test_make_key_length() -> None:
    key = make_key("imgkey01imgkey01", "subkey02subkey02")
    assert len(key) == 32
    assert key.isascii()


def test_encode_value_filters_special_chars() -> None:
    assert encode_value("foo!bar(baz)*") == "foobarbaz"
    assert encode_value("hello world") == "hello%20world"


def test_build_signed_query_contains_signature(monkeypatch) -> None:
    monkeypatch.setattr("utils.bilibili_api.wbi.time.time", lambda: 1700000000)
    query = build_signed_query("0123456789abcdef0123456789abcdef", {"foo": "bar"})
    assert "foo=bar" in query
    assert "wts=1700000000" in query
    assert query.endswith("&w_rid=" + query.split("w_rid=")[-1])
    assert len(query.split("w_rid=")[-1]) == 32
