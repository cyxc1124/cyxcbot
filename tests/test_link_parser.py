"""Tests for utils.bilibili_api.link_parser."""

from __future__ import annotations

from utils.bilibili_api.link_parser import (
    BilibiliRef,
    _dedupe_preserve_order,
    _live_room_id_from_url,
    _video_ref_from_url,
)


def test_video_ref_from_bv_url() -> None:
    ref = _video_ref_from_url("https://www.bilibili.com/video/BV1xx411c7mD")
    assert ref == BilibiliRef(kind="video", bvid="BV1xx411c7mD")


def test_video_ref_from_av_url() -> None:
    ref = _video_ref_from_url("https://m.bilibili.com/video/av170001")
    assert ref == BilibiliRef(kind="video", aid=170001)


def test_video_ref_from_bv_in_text() -> None:
    ref = _video_ref_from_url("看看这个 BV1GJ411x7h7 不错")
    assert ref == BilibiliRef(kind="video", bvid="BV1GJ411x7h7")


def test_live_room_id_from_path() -> None:
    assert _live_room_id_from_url("https://live.bilibili.com/21919321") == 21919321
    assert _live_room_id_from_url("https://live.bilibili.com/blanc/12345") == 12345


def test_live_room_id_from_query() -> None:
    url = "https://live.bilibili.com/h5/123?room_id=99887766"
    assert _live_room_id_from_url(url) == 99887766


def test_dedupe_preserve_order() -> None:
    refs = [
        BilibiliRef(kind="video", bvid="BV1xx411c7mD"),
        BilibiliRef(kind="video", bvid="BV1xx411c7mD"),
        BilibiliRef(kind="live", room_id=123),
    ]
    assert _dedupe_preserve_order(refs) == [
        BilibiliRef(kind="video", bvid="BV1xx411c7mD"),
        BilibiliRef(kind="live", room_id=123),
    ]
