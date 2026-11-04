"""LiveApi.get_room_and_user_info 回退链不应重复请求同一接口。"""

from __future__ import annotations

from collections import Counter
from unittest.mock import AsyncMock

import pytest

from utils.bilibili_api.live_api import LiveApi

ROOM = {"room_id": 1, "live_status": 0, "title": "t"}


def _api(info_by_room, html, get_info):
    api = LiveApi(session=None)  # type: ignore[arg-type]
    api._get_info_by_room = AsyncMock(side_effect=info_by_room)
    api._get_room_page_data_via_html = AsyncMock(side_effect=html)
    api._get_room_info_via_get_info = AsyncMock(side_effect=get_info)
    return api


@pytest.mark.asyncio
async def test_all_endpoints_failing_requests_each_once():
    err = Exception("boom")
    api = _api(err, err, err)
    assert await api.get_room_and_user_info(1) == (None, None)
    calls = Counter(
        info=api._get_info_by_room.await_count,
        html=api._get_room_page_data_via_html.await_count,
        get_info=api._get_room_info_via_get_info.await_count,
    )
    assert calls == {"info": 1, "html": 1, "get_info": 1}


@pytest.mark.asyncio
async def test_get_info_fallback_returns_room_without_user():
    err = Exception("boom")
    api = _api(err, err, [ROOM])
    room, user = await api.get_room_and_user_info(1)
    assert room is not None and room.room_id == 1
    assert user is None
