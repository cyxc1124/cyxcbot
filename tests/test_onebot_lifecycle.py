"""Tests for multi-bot OneBot lifecycle helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.onebot.lifecycle import stop_monitor_if_no_bots


@pytest.mark.asyncio
async def test_stop_monitor_if_no_bots_skips_when_others_online() -> None:
    stop_fn = AsyncMock()
    with patch("shared.onebot.lifecycle.get_bots", return_value={"bot2": MagicMock()}):
        stopped = await stop_monitor_if_no_bots(
            stop_fn,
            bot_self_id="bot1",
            monitor_name="动态监控",
        )

    assert stopped is False
    stop_fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_monitor_if_no_bots_stops_when_last_bot_gone() -> None:
    stop_fn = AsyncMock()
    with patch("shared.onebot.lifecycle.get_bots", return_value={}):
        stopped = await stop_monitor_if_no_bots(
            stop_fn,
            bot_self_id="bot1",
            monitor_name="直播监控",
        )

    assert stopped is True
    stop_fn.assert_awaited_once()
