"""Tests for Rust status output parsing."""

from utils.rust_rcon.status import is_steam_id_online, parse_online_steam_ids

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


def test_parse_online_steam_ids_from_playerlist_json() -> None:
    text = f'[{{"SteamID":"{_STEAM_A}","DisplayName":"Alice"}}]'
    assert parse_online_steam_ids(text) == {_STEAM_A}
