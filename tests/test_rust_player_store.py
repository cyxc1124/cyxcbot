"""Tests for Rust player store helpers."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

if "nonebot_plugin_orm" not in sys.modules:
    sys.modules["nonebot_plugin_orm"] = MagicMock(get_session=MagicMock())

from shared.rust_player.store import _ensure_steam_binding_available


@pytest.mark.asyncio
async def test_ensure_steam_binding_available_rejects_bound_user() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock())

    with pytest.raises(ValueError, match="你已绑定 SteamID"):
        await _ensure_steam_binding_available(session, "123", "76561198000000000")
