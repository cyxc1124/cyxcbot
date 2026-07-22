"""Tests for Rust RCON binding alias validation."""

from __future__ import annotations

import pytest

from shared.config.command_aliases import CommandAliasEntry
from shared.config.rust_rcon import (
    alias_command_conflict,
    normalize_alias,
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
