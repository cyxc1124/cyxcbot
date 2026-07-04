"""Tests for OneBot group list availability signaling."""

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
