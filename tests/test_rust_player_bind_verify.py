"""Tests for Rust player bind verification helpers."""

from __future__ import annotations

import time
from unittest.mock import patch

from shared.rust_player import bind_pending, rcon_online_cache


def test_create_and_consume_pending_bind() -> None:
    bind_pending._pending.clear()
    code = bind_pending.create_pending_bind("123", "76561198000000001")
    assert len(code) == 6

    pending = bind_pending.consume_pending_bind("123")
    assert pending is not None
    assert pending.steam_id == "76561198000000001"
    assert pending.verify_code == code
    assert bind_pending.consume_pending_bind("123") is None


def test_restore_pending_bind_keeps_verify_code() -> None:
    bind_pending._pending.clear()
    code = bind_pending.create_pending_bind("123", "76561198000000001")
    pending = bind_pending.consume_pending_bind("123")
    assert pending is not None

    bind_pending.restore_pending_bind("123", pending)
    restored = bind_pending.consume_pending_bind("123")
    assert restored is not None
    assert restored.verify_code == code


def test_pending_bind_expires() -> None:
    bind_pending._pending.clear()
    bind_pending.create_pending_bind("123", "76561198000000001")
    with patch(
        "shared.rust_player.bind_pending.time.monotonic",
        return_value=time.monotonic() + 601,
    ):
        assert bind_pending.consume_pending_bind("123") is None


def test_checkin_online_cache_ttl() -> None:
    rcon_online_cache._cache.clear()
    rcon_online_cache.set_cached_checkin_online("123", True)
    assert rcon_online_cache.get_cached_checkin_online("123") is True

    with patch(
        "shared.rust_player.rcon_online_cache.time.monotonic",
        return_value=time.monotonic() + 61,
    ):
        assert rcon_online_cache.get_cached_checkin_online("123") is None
