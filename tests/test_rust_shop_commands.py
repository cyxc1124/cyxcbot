"""Tests for Rust shop command parsing."""

from __future__ import annotations

import pytest

import shared.config.command_aliases as command_aliases_module
from shared.config.command_aliases import normalize_command_aliases
from shared.config.rust_player import (
    normalize_shop_item_name,
    parse_shop_list_page,
    parse_shop_redeem_args,
    shop_list_trigger_hint,
)

DEFAULT_ALIASES = normalize_command_aliases({})


def _patch_prefixes(monkeypatch) -> None:
    monkeypatch.setattr(
        command_aliases_module, "_configured_command_starts", lambda: frozenset({"/"})
    )
    monkeypatch.setattr(
        command_aliases_module, "_extra_prefixes", lambda: frozenset({"!"})
    )


def test_parse_shop_list_page_first_page(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_list_page("商品列表", DEFAULT_ALIASES) == 1
    assert parse_shop_list_page("/商品列表", DEFAULT_ALIASES) == 1


def test_parse_shop_list_page_numbered(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_list_page("商品列表2", DEFAULT_ALIASES) == 2
    assert parse_shop_list_page("商品列表10", DEFAULT_ALIASES) == 10
    assert parse_shop_list_page("商品列表0", DEFAULT_ALIASES) is None


def test_parse_shop_list_page_not_matched(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_list_page("商品列表 2", DEFAULT_ALIASES) is None
    assert parse_shop_list_page("兑换商品 wood", DEFAULT_ALIASES) is None


def test_shop_list_trigger_hint() -> None:
    assert shop_list_trigger_hint(DEFAULT_ALIASES) == "商品列表"


def test_parse_shop_redeem_by_item_id(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_redeem_args("兑换商品 wood", DEFAULT_ALIASES) == ("wood", 1)
    assert parse_shop_redeem_args("兑换商品 rifle.ak 3", DEFAULT_ALIASES) == (
        "rifle.ak",
        3,
    )


def test_parse_shop_redeem_by_name(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_redeem_args("兑换商品 木头 5", DEFAULT_ALIASES) == ("木头", 5)
    assert parse_shop_redeem_args("兑换商品 AK步枪", DEFAULT_ALIASES) == ("AK步枪", 1)
    # 商品名禁止以「空格+数字」结尾；此处按 identifier + quantity 解析
    assert parse_shop_redeem_args("兑换商品 AK 47", DEFAULT_ALIASES) == ("AK", 47)


@pytest.mark.parametrize("name", ["步枪 M249", "AK  步枪", "AK\t步枪", "wood 2.5"])
def test_parse_shop_redeem_preserves_accepted_name(monkeypatch, name: str) -> None:
    _patch_prefixes(monkeypatch)
    saved_name = normalize_shop_item_name(name)
    assert parse_shop_redeem_args(f"兑换商品 {saved_name}", DEFAULT_ALIASES) == (
        saved_name,
        1,
    )
    assert parse_shop_redeem_args(f"/兑换商品 {saved_name} 3", DEFAULT_ALIASES) == (
        saved_name,
        3,
    )


def test_parse_shop_redeem_quantity_limit(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_redeem_args("兑换商品 AK  步枪 1000", DEFAULT_ALIASES) == (
        "AK  步枪",
        1000,
    )
    assert parse_shop_redeem_args("兑换商品 AK  步枪 1001", DEFAULT_ALIASES) is None


def test_parse_shop_redeem_invalid(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_redeem_args("兑换商品", DEFAULT_ALIASES) is None
    assert parse_shop_redeem_args("兑换商品 木头 0", DEFAULT_ALIASES) is None
