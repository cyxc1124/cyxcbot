"""Tests for Rust player command parsing and SteamID validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import shared.config.command_aliases as command_aliases_module
from admin.schemas.rust_player import RustPlayerPointsUpdateRequest
from shared.config.command_aliases import normalize_command_aliases
from shared.config.rust_player import (
    is_bind_command,
    is_checkin_command,
    is_points_query_command,
    is_rust_player_command,
    normalize_checkin_online_bonus,
    normalize_checkin_points_range,
    normalize_checkin_rcon_binding_id,
    normalize_player_points,
    normalize_steam_id,
    parse_bind_steam_id,
    resolve_checkin_rcon_binding,
)
from shared.config.rust_rcon import RustRconBindingRecord, alias_command_conflict
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


def test_is_rust_player_command(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert is_rust_player_command("签到", DEFAULT_ALIASES)
    assert is_rust_player_command("商品列表2", DEFAULT_ALIASES)
    assert is_rust_player_command("兑换商品 wood", DEFAULT_ALIASES)
    assert not is_rust_player_command("hello", DEFAULT_ALIASES)


def test_normalize_checkin_points_range() -> None:
    assert normalize_checkin_points_range(1, 10) == (1, 10)
    try:
        normalize_checkin_points_range(5, 1)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        normalize_checkin_points_range(0, 1_000_001)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "1000000" in str(exc)


def test_normalize_player_points_rejects_overflow() -> None:
    with pytest.raises(ValueError, match="1000000"):
        normalize_player_points(1_000_001)


def test_rust_player_points_schema_uses_chinese_limit_error() -> None:
    with pytest.raises(ValidationError, match="积分不能超过 1000000"):
        RustPlayerPointsUpdateRequest(
            group_id="123456",
            user_id="654321",
            points=1_000_001,
        )


def test_normalize_checkin_online_bonus() -> None:
    assert normalize_checkin_online_bonus(50) == 50
    with pytest.raises(ValueError, match="1000000"):
        normalize_checkin_online_bonus(1_000_001)


def test_resolve_checkin_rcon_binding() -> None:
    bindings = [
        RustRconBindingRecord(
            id=1,
            alias="a",
            host="1.1.1.1",
            port=28016,
            password="x",
            enabled=False,
        ),
        RustRconBindingRecord(
            id=2,
            alias="b",
            host="2.2.2.2",
            port=28016,
            password="x",
            enabled=True,
        ),
        RustRconBindingRecord(
            id=3,
            alias="c",
            host="3.3.3.3",
            port=28016,
            password="x",
            enabled=True,
        ),
    ]
    assert resolve_checkin_rcon_binding(bindings, 0).id == 2
    assert resolve_checkin_rcon_binding(bindings, 3).id == 3
    assert resolve_checkin_rcon_binding(bindings, 99) is None
    assert resolve_checkin_rcon_binding([], 0) is None


def test_resolve_checkin_rcon_binding_picks_lowest_id_when_unsorted() -> None:
    bindings = [
        RustRconBindingRecord(
            id=3,
            alias="c",
            host="3.3.3.3",
            port=28016,
            password="x",
            enabled=True,
        ),
        RustRconBindingRecord(
            id=2,
            alias="b",
            host="2.2.2.2",
            port=28016,
            password="x",
            enabled=True,
        ),
    ]
    assert resolve_checkin_rcon_binding(bindings, 0).id == 2


def test_normalize_checkin_rcon_binding_id() -> None:
    assert normalize_checkin_rcon_binding_id(0) == 0
    with pytest.raises(ValueError):
        normalize_checkin_rcon_binding_id(-1)


def test_rust_player_triggers_conflict_with_rcon_alias() -> None:
    snap = AppConfigSnapshot(command_aliases=DEFAULT_ALIASES)
    assert alias_command_conflict("签到", snap) is not None
    assert alias_command_conflict("绑定", snap) is not None
    assert alias_command_conflict("积分", snap) is not None
