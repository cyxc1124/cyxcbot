"""Tests for Rust shop store helpers."""

from __future__ import annotations

import pytest

from shared.config.rust_player import (
    MAX_SQL_INTEGER,
    MIN_SQL_INTEGER,
    normalize_shop_item_id,
    normalize_shop_item_name,
    normalize_shop_points_cost,
    normalize_shop_quantity,
    normalize_shop_sort_order,
    shop_item_integrity_error_message,
)


def test_normalize_shop_item_name() -> None:
    assert normalize_shop_item_name("  木头  ") == "木头"
    assert normalize_shop_item_name("AK47") == "AK47"
    assert normalize_shop_item_name("AK 步枪") == "AK 步枪"
    with pytest.raises(ValueError, match="不能为空"):
        normalize_shop_item_name("   ")
    with pytest.raises(ValueError, match="空格加数字"):
        normalize_shop_item_name("AK 47")


def test_normalize_shop_item_id() -> None:
    assert normalize_shop_item_id(" rifle.ak ") == "rifle.ak"
    with pytest.raises(ValueError, match="不能为空"):
        normalize_shop_item_id("")


def test_normalize_shop_points_cost() -> None:
    assert normalize_shop_points_cost(10) == 10
    with pytest.raises(ValueError, match="必须大于 0"):
        normalize_shop_points_cost(0)


def test_normalize_shop_sort_order() -> None:
    assert normalize_shop_sort_order(0) == 0
    assert normalize_shop_sort_order(MAX_SQL_INTEGER) == MAX_SQL_INTEGER
    assert normalize_shop_sort_order(MIN_SQL_INTEGER) == MIN_SQL_INTEGER
    with pytest.raises(ValueError, match="排序值"):
        normalize_shop_sort_order(MAX_SQL_INTEGER + 1)
    with pytest.raises(ValueError, match="排序值"):
        normalize_shop_sort_order(MIN_SQL_INTEGER - 1)


def test_normalize_shop_quantity() -> None:
    assert normalize_shop_quantity(1) == 1
    with pytest.raises(ValueError, match="至少为 1"):
        normalize_shop_quantity(0)
    with pytest.raises(ValueError, match="1000"):
        normalize_shop_quantity(1001)


def test_shop_item_integrity_error_message() -> None:
    assert (
        shop_item_integrity_error_message(Exception("uq_rust_shop_enabled_name"))
        == "已存在同名的启用商品"
    )
    assert (
        shop_item_integrity_error_message(
            Exception("UNIQUE constraint failed: shared_db_rustshopitem.item_id")
        )
        == "物品 ID 已存在"
    )
