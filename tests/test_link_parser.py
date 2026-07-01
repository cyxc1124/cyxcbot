"""Tests for utils.bilibili_api.link_parser."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from utils.bilibili_api.link_parser import (
    BilibiliRef,
    _dedupe_preserve_order,
    _live_room_id_from_url,
    _video_ref_from_url,
    extract_bilibili_refs,
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


@pytest.mark.asyncio
async def test_extract_bilibili_refs_caps_b23_resolve_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve_calls: list[str] = []

    async def fake_resolve(
        _session: object, url: str, *, cookie: str | None = None
    ) -> str:
        resolve_calls.append(url)
        return "https://www.bilibili.com/video/BV1xx411c7mD"

    monkeypatch.setattr(
        "utils.bilibili_api.link_parser.resolve_short_url", fake_resolve
    )

    text = " ".join(f"https://b23.tv/abc{i}" for i in range(20))
    refs = await extract_bilibili_refs(text, MagicMock(), max_count=3)

    assert len(resolve_calls) == 3
    assert len(refs) == 1


@pytest.mark.asyncio
async def test_extract_bilibili_refs_b23_respects_existing_ref_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve_calls: list[str] = []

    async def fake_resolve(
        _session: object, url: str, *, cookie: str | None = None
    ) -> str:
        resolve_calls.append(url)
        return "https://www.bilibili.com/video/BV1yy411c7mE"

    monkeypatch.setattr(
        "utils.bilibili_api.link_parser.resolve_short_url", fake_resolve
    )

    text = "BV1xx411c7mD BV1zz411c7mF " + " ".join(
        f"https://b23.tv/abc{i}" for i in range(10)
    )
    refs = await extract_bilibili_refs(text, MagicMock(), max_count=3)

    assert len(resolve_calls) == 1
    assert refs == [
        BilibiliRef(kind="video", bvid="BV1xx411c7mD"),
        BilibiliRef(kind="video", bvid="BV1zz411c7mF"),
        BilibiliRef(kind="video", bvid="BV1yy411c7mE"),
    ]


@pytest.mark.asyncio
async def test_extract_bilibili_refs_b23_resolve_is_bounded_concurrent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_flight = 0
    peak = 0

    async def fake_resolve(
        _session: object, url: str, *, cookie: str | None = None
    ) -> str:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return "https://www.bilibili.com/video/BV1xx411c7mD"

    monkeypatch.setattr(
        "utils.bilibili_api.link_parser.resolve_short_url", fake_resolve
    )

    text = " ".join(f"https://b23.tv/abc{i}" for i in range(6))
    await extract_bilibili_refs(text, MagicMock(), max_count=3)

    assert peak <= 3
