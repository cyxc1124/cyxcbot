"""Tests for Rust check-in RCON online cache."""

from __future__ import annotations

import time
from unittest.mock import patch

from shared.rust_player import rcon_online_cache


def test_checkin_online_cache_ttl() -> None:
    rcon_online_cache._cache.clear()
    rcon_online_cache.set_cached_checkin_online("123", True)
    assert rcon_online_cache.get_cached_checkin_online("123") is True

    with patch(
        "shared.rust_player.rcon_online_cache.time.monotonic",
        return_value=time.monotonic() + 61,
    ):
        assert rcon_online_cache.get_cached_checkin_online("123") is None
