"""Tests for Rust RCON per-chat policy resolution."""

from __future__ import annotations

from shared.config.rust_rcon_policy import (
    RustRconGroupPolicyRecord,
    RustRconUserPolicyRecord,
    is_rust_rcon_enabled,
)
from shared.config.types import AppConfigSnapshot


def test_rust_rcon_disabled_by_default() -> None:
    snap = AppConfigSnapshot()
    assert not is_rust_rcon_enabled(snap, group_id="123")
    assert not is_rust_rcon_enabled(snap, user_id="456", is_private=True)


def test_rust_rcon_group_override() -> None:
    snap = AppConfigSnapshot(
        rust_rcon_group_policies={
            "123": RustRconGroupPolicyRecord(group_id="123", enabled=True),
        }
    )
    assert is_rust_rcon_enabled(snap, group_id="123")
    assert not is_rust_rcon_enabled(snap, group_id="999")


def test_rust_rcon_user_override() -> None:
    snap = AppConfigSnapshot(
        rust_rcon_user_policies={
            "456": RustRconUserPolicyRecord(user_id="456", enabled=True),
        }
    )
    assert is_rust_rcon_enabled(snap, user_id="456", is_private=True)
    assert not is_rust_rcon_enabled(snap, user_id="999", is_private=True)
