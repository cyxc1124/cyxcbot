"""Tests for Rust player command parsing and SteamID validation."""

from __future__ import annotations

import shared.config.command_aliases as command_aliases_module
from shared.config.command_aliases import normalize_command_aliases
from shared.config.rust_player import (
    is_bind_command,
    is_checkin_command,
    is_points_query_command,
    normalize_checkin_points_range,
    normalize_steam_id,
    parse_bind_steam_id,
)
from shared.config.rust_rcon import alias_command_conflict
from shared.config.types import AppConfigSnapshot

_VALID_STEAM = "76561198000000000"
DEFAULT_ALIASES = normalize_command_aliases({})


def _patch_prefixes(monkeypatch) -> None:
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"/"})
    )
    monkeypatch.setattr(
        command_aliases_module, "_extra_prefixes", lambda: frozenset({"!"})
    )


def test_normalize_steam_id_valid() -> None:
    assert normalize_steam_id(_VALID_STEAM) == _VALID_STEAM


def test_normalize_steam_id_rejects_invalid() -> None:
    assert normalize_steam_id("123") is None
    assert normalize_steam_id("7656119800000000") is None


def test_parse_bind_steam_id(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_bind_steam_id(f"绑定 {_VALID_STEAM}", DEFAULT_ALIASES) == _VALID_STEAM
    assert parse_bind_steam_id(f"/绑定 {_VALID_STEAM}", DEFAULT_ALIASES) == _VALID_STEAM
    assert parse_bind_steam_id("绑定 invalid", DEFAULT_ALIASES) is None
    assert parse_bind_steam_id("绑定", DEFAULT_ALIASES) is None


def test_parse_bind_steam_id_custom_trigger(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    config = normalize_command_aliases(
        {"rust_player_bind": {"enabled": True, "triggers": ["linksteam"]}}
    )
    assert parse_bind_steam_id(f"linksteam {_VALID_STEAM}", config) == _VALID_STEAM


def test_is_bind_command(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert is_bind_command("绑定", DEFAULT_ALIASES)
    assert is_bind_command(f"绑定 {_VALID_STEAM}", DEFAULT_ALIASES)
    assert not is_bind_command("绑定x", DEFAULT_ALIASES)


def test_is_checkin_command(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert is_checkin_command("签到", DEFAULT_ALIASES)
    assert is_checkin_command("/签到", DEFAULT_ALIASES)
    assert is_checkin_command("签到啦", DEFAULT_ALIASES)


def test_is_points_query_command(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert is_points_query_command("积分", DEFAULT_ALIASES)
    assert is_points_query_command("我的积分", DEFAULT_ALIASES)
    assert is_points_query_command("查积分", DEFAULT_ALIASES)


def test_normalize_checkin_points_range() -> None:
    assert normalize_checkin_points_range(1, 10) == (1, 10)
    try:
        normalize_checkin_points_range(5, 1)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_rust_player_triggers_conflict_with_rcon_alias() -> None:
    snap = AppConfigSnapshot(command_aliases=DEFAULT_ALIASES)
    assert alias_command_conflict("签到", snap) is not None
    assert alias_command_conflict("绑定", snap) is not None
    assert alias_command_conflict("积分", snap) is not None
