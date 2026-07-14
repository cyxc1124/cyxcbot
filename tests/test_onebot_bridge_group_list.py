"""Tests for OneBot group/friend list availability signaling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from admin.services import onebot_bridge


@pytest.mark.asyncio
async def test_group_list_unavailable_when_any_bot_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot_ok = MagicMock()
    bot_ok.self_id = "1"
    bot_ok.call_api = AsyncMock(
        return_value=[{"group_id": 123, "group_name": "a", "member_count": 1}]
    )
    bot_fail = MagicMock()
    bot_fail.self_id = "2"
    bot_fail.call_api = AsyncMock(side_effect=RuntimeError("down"))

    monkeypatch.setattr(
        onebot_bridge,
        "get_bots",
        lambda: {"1": bot_ok, "2": bot_fail},
    )

    groups, available = await onebot_bridge.get_group_list_with_availability()

    assert available is False
    assert groups == [
        {"group_id": "123", "group_name": "a", "member_count": 1},
    ]


@pytest.mark.asyncio
async def test_group_list_available_when_all_bots_succeed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = MagicMock()
    bot.self_id = "1"
    bot.call_api = AsyncMock(return_value=[])

    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {"1": bot})

    groups, available = await onebot_bridge.get_group_list_with_availability()

    assert available is True
    assert groups == []


@pytest.fixture(autouse=True)
def _clear_friend_list_cache() -> None:
    onebot_bridge.invalidate_user_list_cache()
    yield
    onebot_bridge.invalidate_user_list_cache()


@pytest.mark.asyncio
async def test_friend_list_offline_when_no_bots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {})

    users, status = await onebot_bridge.get_friend_list_with_availability()

    assert status == "offline"
    assert users == []


@pytest.mark.asyncio
async def test_friend_list_incomplete_when_any_bot_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot_ok = MagicMock()
    bot_ok.self_id = "1"
    bot_ok.call_api = AsyncMock(
        return_value=[{"user_id": 10001, "nickname": "a", "remark": ""}]
    )
    bot_fail = MagicMock()
    bot_fail.self_id = "2"
    bot_fail.call_api = AsyncMock(side_effect=RuntimeError("down"))

    monkeypatch.setattr(
        onebot_bridge,
        "get_bots",
        lambda: {"1": bot_ok, "2": bot_fail},
    )

    users, status = await onebot_bridge.get_friend_list_with_availability()

    assert status == "incomplete"
    assert users == [{"user_id": "10001", "nickname": "a"}]
    # Incomplete results must not be cached.
    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {})
    users2, status2 = await onebot_bridge.get_friend_list_with_availability()
    assert status2 == "offline"
    assert users2 == []


@pytest.mark.asyncio
async def test_friend_list_ok_when_all_bots_succeed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = MagicMock()
    bot.self_id = "1"
    bot.call_api = AsyncMock(return_value=[])

    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {"1": bot})

    users, status = await onebot_bridge.get_friend_list_with_availability()

    assert status == "ok"
    assert users == []
