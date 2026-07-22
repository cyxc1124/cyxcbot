"""Tests for Rust player command parsing and SteamID validation."""

from __future__ import annotations

from shared.config.rust_player import (
    is_bind_command,
    is_checkin_command,
    is_points_query_command,
    normalize_checkin_points_range,
    normalize_steam_id,
    parse_bind_steam_id,
)

_VALID_STEAM = "76561198000000000"


def test_normalize_steam_id_valid() -> None:
    assert normalize_steam_id(_VALID_STEAM) == _VALID_STEAM


def test_normalize_steam_id_rejects_invalid() -> None:
    assert normalize_steam_id("123") is None
    assert normalize_steam_id("7656119800000000") is None


def test_parse_bind_steam_id() -> None:
    assert parse_bind_steam_id(f"绑定 {_VALID_STEAM}") == _VALID_STEAM
    assert parse_bind_steam_id(f"/绑定 {_VALID_STEAM}") == _VALID_STEAM
    assert parse_bind_steam_id("绑定 invalid") is None
    assert parse_bind_steam_id("绑定") is None


def test_is_bind_command() -> None:
    assert is_bind_command("绑定")
    assert is_bind_command(f"绑定 {_VALID_STEAM}")
    assert not is_bind_command("绑定x")


def test_is_checkin_command() -> None:
    assert is_checkin_command("签到")
    assert is_checkin_command("/签到")
    assert not is_checkin_command("签到啦")


def test_is_points_query_command() -> None:
    assert is_points_query_command("积分")
    assert is_points_query_command("我的积分")
    assert not is_points_query_command("查积分")


def test_normalize_checkin_points_range() -> None:
    assert normalize_checkin_points_range(1, 10) == (1, 10)
    try:
        normalize_checkin_points_range(5, 1)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
