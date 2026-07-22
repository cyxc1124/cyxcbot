"""Tests for Rust RCON binding alias validation."""

from __future__ import annotations

import pytest

from shared.config.command_aliases import CommandAliasEntry
from shared.config.rust_rcon import (
    alias_command_conflict,
    normalize_alias,
    normalize_allowed_qq_ids,
    normalize_port,
)
from shared.config.types import AppConfigSnapshot


def test_normalize_alias_rejects_empty() -> None:
    with pytest.raises(ValueError, match="不能为空"):
        normalize_alias("  ")


def test_normalize_alias_rejects_whitespace() -> None:
    with pytest.raises(ValueError, match="空白"):
        normalize_alias("rcon 1")


def test_normalize_port_range() -> None:
    assert normalize_port(28016) == 28016
    with pytest.raises(ValueError):
        normalize_port(0)
    with pytest.raises(ValueError):
        normalize_port(70000)


def test_alias_command_conflict() -> None:
    snap = AppConfigSnapshot(
        command_aliases={
            "status": CommandAliasEntry(enabled=True, triggers=["status", "rcon1"]),
        }
    )
    assert alias_command_conflict("status", snap) is not None
    assert alias_command_conflict("rcon1", snap) is not None
    assert alias_command_conflict("rcon2", snap) is None


def test_alias_command_conflict_ignores_disabled() -> None:
    snap = AppConfigSnapshot(
        command_aliases={
            "status": CommandAliasEntry(enabled=False, triggers=["rcon1"]),
        }
    )
    assert alias_command_conflict("rcon1", snap) is None


def test_normalize_allowed_qq_ids() -> None:
    assert normalize_allowed_qq_ids(["123", "456", "123"]) == ["123", "456"]
    with pytest.raises(ValueError, match="至少"):
        normalize_allowed_qq_ids([])
    with pytest.raises(ValueError, match="格式无效"):
        normalize_allowed_qq_ids(["abc"])


def test_is_qq_allowed_for_binding() -> None:
    from shared.config.rust_rcon import RustRconBindingRecord, is_qq_allowed_for_binding

    binding = RustRconBindingRecord(
        id=1,
        alias="rcon1",
        host="127.0.0.1",
        port=28016,
        password="secret",
        allowed_qq_ids=("123", "456"),
    )
    assert is_qq_allowed_for_binding(binding, "123")
    assert not is_qq_allowed_for_binding(binding, "999")
