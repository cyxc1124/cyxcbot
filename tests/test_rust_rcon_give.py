"""Tests for Rust give RCON response parsing."""

from __future__ import annotations

import pytest

from utils.rust_rcon.give import (
    normalize_give_quantity,
    parse_give_rejection,
    parse_quantity_token,
)


def test_parse_give_rejection_player_offline() -> None:
    assert parse_give_rejection("Couldn't find player!") == "玩家不在线"


def test_parse_give_rejection_invalid_item() -> None:
    assert parse_give_rejection("Invalid Item!") == "物品 ID 无效"


def test_parse_give_rejection_success() -> None:
    assert parse_give_rejection("giving wood x5") is None
    assert parse_give_rejection("") is None


def test_parse_quantity_token() -> None:
    assert parse_quantity_token("5") == 5
    assert parse_quantity_token("0") == 0
    assert parse_quantity_token("1.5") is None
    assert parse_quantity_token("-1") is None


def test_normalize_give_quantity() -> None:
    assert normalize_give_quantity(0) == 0
    assert normalize_give_quantity(10) == 10
    with pytest.raises(ValueError, match="小数"):
        normalize_give_quantity(1.5)
    with pytest.raises(ValueError, match="负数"):
        normalize_give_quantity(-1)
