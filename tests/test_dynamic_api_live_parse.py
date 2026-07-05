"""Tests for live-dynamic parsing in DynamicFetcher."""

from __future__ import annotations

import json

from utils.bilibili_api.dynamic_api import DynamicFetcher


def _live_rcmd_item() -> dict:
    live_play_info = {
        "room_id": 21919321,
        "title": "晚间聊天",
        "cover": "https://i0.hdslb.com/bfs/live/cover.jpg",
        "area_name": "虚拟主播",
        "watched_show": {"text_large": "1.2万人看过"},
    }
    return {
        "id_str": "718371505648435205",
        "type": "DYNAMIC_TYPE_LIVE_RCMD",
        "pub_ts": 1710000000,
        "modules": {
            "module_author": {
                "mid": 12345,
                "name": "测试主播",
            },
            "module_dynamic": {
                "major": {
                    "type": "MAJOR_TYPE_LIVE_RCMD",
                    "live_rcmd": {
                        "content": json.dumps({"live_play_info": live_play_info}),
                    },
                },
            },
        },
    }


def _live_share_item() -> dict:
    return {
        "id_str": "267505569812738175",
        "type": "DYNAMIC_TYPE_LIVE",
        "pub_ts": 1710000001,
        "modules": {
            "module_author": {
                "mid": 67890,
                "name": "分享主播",
            },
            "module_dynamic": {
                "major": {
                    "type": "MAJOR_TYPE_LIVE",
                    "live": {
                        "id": 99887766,
                        "title": "直播间分享标题",
                        "cover": "https://i0.hdslb.com/bfs/live/share.jpg",
                    },
                },
            },
        },
    }


async def _parse(item: dict, *, skip_live_dynamic: bool = True):
    fetcher = DynamicFetcher(session=None)  # type: ignore[arg-type]
    return await fetcher._parse_dynamic_item(
        item,
        uid="0",
        skip_live_dynamic=skip_live_dynamic,
    )


async def test_parse_live_dynamic_skipped_for_monitor() -> None:
    assert await _parse(_live_rcmd_item()) is None
    assert await _parse(_live_share_item()) is None


async def test_parse_live_rcmd_for_link_parser() -> None:
    item = await _parse(_live_rcmd_item(), skip_live_dynamic=False)
    assert item is not None
    assert item.live_room_id == 21919321
    assert item.title == "晚间聊天"
    assert item.body_text == "虚拟主播 · 1.2万人看过"
    assert item.images == ["https://i0.hdslb.com/bfs/live/cover.jpg"]
    assert item.url == "https://live.bilibili.com/21919321"


async def test_parse_live_share_for_link_parser() -> None:
    item = await _parse(_live_share_item(), skip_live_dynamic=False)
    assert item is not None
    assert item.live_room_id == 99887766
    assert item.title == "直播间分享标题"
    assert item.url == "https://live.bilibili.com/99887766"
