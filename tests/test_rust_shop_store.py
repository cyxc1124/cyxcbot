"""Tests for Rust shop store helpers."""

from __future__ import annotations

import pytest

from shared.config.rust_player import (
    normalize_shop_item_id,
    normalize_shop_item_name,
    normalize_shop_quantity,
    normalize_shop_points_cost,
)


def test_normalize_shop_item_name() -> None:
    assert normalize_shop_item_name("  木头  ") == "木头"
    with pytest.raises(ValueError, match="不能为空"):
        normalize_shop_item_name("   ")


def test_normalize_shop_item_id() -> None:
    assert normalize_shop_item_id(" rifle.ak ") == "rifle.ak"
    with pytest.raises(ValueError, match="不能为空"):
        normalize_shop_item_id("")


def test_normalize_shop_points_cost() -> None:
    assert normalize_shop_points_cost(10) == 10
    with pytest.raises(ValueError, match="必须大于 0"):
        normalize_shop_points_cost(0)


def test_normalize_shop_quantity() -> None:
    assert normalize_shop_quantity(1) == 1
    with pytest.raises(ValueError, match="至少为 1"):
        normalize_shop_quantity(0)
    with pytest.raises(ValueError, match="1000"):
        normalize_shop_quantity(1001)
