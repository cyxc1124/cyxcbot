"""Tests for Rust status output parsing."""

from utils.rust_rcon.status import (
    get_player_display_name,
    is_steam_id_online,
    parse_online_steam_ids,
    player_display_name_contains_code,
)

_STEAM_A = "76561198000000001"
_STEAM_B = "76561198000000002"

_STATUS_SAMPLE = f"""
hostname: Test Server
version : 2583 secure (secure mode enabled, connected to Steam3)
map     : Procedural Map
players : 2 (100 max) (0 queued) (0 joining)

id name ping connected addr owner violation kicks
{_STEAM_A} "Alice" 28 300.99s 127.0.0.1:12345 0 0.0 0
{_STEAM_B} "Bob" 31 120.00s 127.0.0.1:54321 0 0.0 0
"""


def test_parse_online_steam_ids_from_status() -> None:
    assert parse_online_steam_ids(_STATUS_SAMPLE) == {_STEAM_A, _STEAM_B}


def test_is_steam_id_online() -> None:
    assert is_steam_id_online(_STATUS_SAMPLE, _STEAM_A) is True
    assert is_steam_id_online(_STATUS_SAMPLE, "76561198000000999") is False
    assert is_steam_id_online(_STATUS_SAMPLE, "invalid") is False


def test_parse_online_steam_ids_ignores_nickname_embedded_steam_id() -> None:
    """Nickname must not count as the player id column."""
    text = f'{_STEAM_B} "{_STEAM_A}" 28 300.99s 127.0.0.1:12345 0 0.0 0'
    assert parse_online_steam_ids(text) == {_STEAM_B}
    assert is_steam_id_online(text, _STEAM_A) is False
    assert is_steam_id_online(text, _STEAM_B) is True


def test_parse_online_steam_ids_ignores_non_player_lines() -> None:
    text = f'players : 1 (100 max)\nSteamID in json: "{_STEAM_A}"'
    assert parse_online_steam_ids(text) == set()


def test_get_player_display_name() -> None:
    assert get_player_display_name(_STATUS_SAMPLE, _STEAM_A) == "Alice"
    assert get_player_display_name(_STATUS_SAMPLE, "76561198000000999") is None


def test_player_display_name_contains_code() -> None:
    text = f'{_STEAM_A} "Player-ABC123" 28 300.99s 127.0.0.1:12345 0 0.0 0'
    assert player_display_name_contains_code(text, _STEAM_A, "abc123") is True
    assert player_display_name_contains_code(text, _STEAM_A, "ZZZZZZ") is False
    assert player_display_name_contains_code(text, _STEAM_B, "ABC123") is False
