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


@pytest.mark.asyncio
async def test_friend_list_cache_rejects_stale_ok_after_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = MagicMock()
    bot.self_id = "1"
    bot.call_api = AsyncMock(
        return_value=[{"user_id": 10001, "nickname": "a", "remark": ""}]
    )
    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {"1": bot})

    users, status = await onebot_bridge.get_friend_list_with_availability()
    assert status == "ok"
    assert users == [{"user_id": "10001", "nickname": "a"}]

    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {})
    users2, status2 = await onebot_bridge.get_friend_list_with_availability()
    assert status2 == "offline"
    assert users2 == []


@pytest.mark.asyncio
async def test_friend_list_cache_refetches_when_bot_set_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot1 = MagicMock()
    bot1.self_id = "1"
    bot1.call_api = AsyncMock(
        return_value=[{"user_id": 10001, "nickname": "a", "remark": ""}]
    )
    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {"1": bot1})
    users, status = await onebot_bridge.get_friend_list_with_availability()
    assert status == "ok"
    assert users == [{"user_id": "10001", "nickname": "a"}]

    bot2 = MagicMock()
    bot2.self_id = "2"
    bot2.call_api = AsyncMock(
        return_value=[{"user_id": 20002, "nickname": "b", "remark": ""}]
    )
    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {"2": bot2})
    users2, status2 = await onebot_bridge.get_friend_list_with_availability()
    assert status2 == "ok"
    assert users2 == [{"user_id": "20002", "nickname": "b"}]
    assert bot2.call_api.await_count == 1


@pytest.mark.asyncio
async def test_group_list_status_offline_when_no_bots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(onebot_bridge, "get_bots", lambda: {})
    groups, status = await onebot_bridge.get_group_list_with_status()
    assert status == "offline"
    assert groups == []


@pytest.mark.asyncio
async def test_group_list_status_incomplete_when_any_bot_fails(
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
    groups, status = await onebot_bridge.get_group_list_with_status()
    assert status == "incomplete"
    assert groups == [{"group_id": "123", "group_name": "a", "member_count": 1}]
