"""Tests for Rust shop command parsing."""

from __future__ import annotations

import shared.config.command_aliases as command_aliases_module
from shared.config.command_aliases import normalize_command_aliases
from shared.config.rust_player import (
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


def test_parse_shop_redeem_invalid(monkeypatch) -> None:
    _patch_prefixes(monkeypatch)
    assert parse_shop_redeem_args("兑换商品", DEFAULT_ALIASES) is None
    assert parse_shop_redeem_args("兑换商品 木头 0", DEFAULT_ALIASES) is None
    assert parse_shop_redeem_args("兑换商品 wood 2.5", DEFAULT_ALIASES) is None
