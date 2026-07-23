"""Rust player command parsing and SteamID validation."""

from __future__ import annotations

import re
from typing import Dict

from shared.config.command_aliases import (
    CommandAliasEntry,
    match_command_arg,
    match_plain,
    resolve_entry,
)
from shared.config.rust_rcon import RustRconBindingRecord

STEAM_ID64_RE = re.compile(r"^7656119\d{10}$")
MAX_RUST_PLAYER_POINTS = 1_000_000
MAX_SHOP_REDEEM_QUANTITY = 1000


def normalize_steam_id(raw: str) -> str | None:
    steam_id = str(raw).strip()
    if STEAM_ID64_RE.fullmatch(steam_id):
        return steam_id
    return None


def bind_trigger_hint(command_aliases: Dict[str, CommandAliasEntry]) -> str:
    entry = resolve_entry("rust_player_bind", command_aliases)
    return entry.triggers[0] if entry.triggers else "绑定"


def is_bind_command(text: str, command_aliases: Dict[str, CommandAliasEntry]) -> bool:
    return match_command_arg(text, "rust_player_bind", command_aliases) is not None


def parse_bind_steam_id(
    text: str, command_aliases: Dict[str, CommandAliasEntry]
) -> str | None:
    arg = match_command_arg(text, "rust_player_bind", command_aliases)
    if arg is None or not arg:
        return None
    return normalize_steam_id(arg)


def is_checkin_command(
    text: str, command_aliases: Dict[str, CommandAliasEntry]
) -> bool:
    return match_plain(text, "rust_player_checkin", command_aliases, is_tome=True)


def is_points_query_command(
    text: str, command_aliases: Dict[str, CommandAliasEntry]
) -> bool:
    return match_plain(text, "rust_player_points", command_aliases, is_tome=True)


def is_rust_player_command(
    text: str, command_aliases: Dict[str, CommandAliasEntry]
) -> bool:
    """Whether *text* matches any Rust 群管 command trigger."""
    return (
        is_bind_command(text, command_aliases)
        or parse_bind_steam_id(text, command_aliases) is not None
        or is_checkin_command(text, command_aliases)
        or is_points_query_command(text, command_aliases)
        or parse_shop_list_page(text, command_aliases) is not None
        or parse_shop_redeem_args(text, command_aliases) is not None
    )


def shop_list_trigger_hint(command_aliases: Dict[str, CommandAliasEntry]) -> str:
    entry = resolve_entry("rust_player_shop_list", command_aliases)
    return entry.triggers[0] if entry.triggers else "商品列表"


def parse_shop_list_page(
    text: str, command_aliases: Dict[str, CommandAliasEntry]
) -> int | None:
    """Match shop list command; return 1-based page number or None."""
    entry = resolve_entry("rust_player_shop_list", command_aliases)
    if not entry.enabled or not entry.triggers:
        return None
    text = text.strip()
    candidates = [text]
    from shared.config.command_aliases import _strip_command_prefix

    stripped = _strip_command_prefix(text)
    if stripped is not None:
        candidates.append(stripped.strip())
    for candidate in candidates:
        for trigger in sorted(entry.triggers, key=len, reverse=True):
            if candidate == trigger:
                return 1
            if candidate.startswith(trigger):
                suffix = candidate[len(trigger) :]
                if not suffix:
                    return 1
                if suffix.isdigit():
                    page = int(suffix)
                    return page if page >= 1 else None
    return None


def shop_redeem_trigger_hint(command_aliases: Dict[str, CommandAliasEntry]) -> str:
    entry = resolve_entry("rust_player_shop_redeem", command_aliases)
    return entry.triggers[0] if entry.triggers else "兑换商品"


def parse_shop_redeem_args(
    text: str, command_aliases: Dict[str, CommandAliasEntry]
) -> tuple[str, int] | None:
    """Return ``(identifier, quantity)`` when redeem command matches."""
    from utils.rust_rcon.give import parse_quantity_token

    arg = match_command_arg(text, "rust_player_shop_redeem", command_aliases)
    if arg is None or not arg.strip():
        return None
    parts = arg.split()
    if len(parts) == 1:
        return parts[0], 1
    last = parts[-1]
    quantity_token = parse_quantity_token(last)
    if quantity_token is not None:
        identifier = " ".join(parts[:-1]).strip()
        if not identifier:
            return None
        try:
            quantity = normalize_shop_quantity(quantity_token)
        except ValueError:
            return None
        return identifier, quantity
    if any(ch.isdigit() for ch in last):
        return None
    return " ".join(parts), 1


def normalize_shop_quantity(quantity: int) -> int:
    from utils.rust_rcon.give import normalize_give_quantity

    value = normalize_give_quantity(quantity)
    if value < 1:
        raise ValueError("兑换数量至少为 1")
    if value > MAX_SHOP_REDEEM_QUANTITY:
        raise ValueError(f"单次兑换数量不能超过 {MAX_SHOP_REDEEM_QUANTITY}")
    return value


def normalize_shop_item_name(name: str) -> str:
    value = str(name).strip()
    if not value:
        raise ValueError("商品中文名不能为空")
    if len(value) > 128:
        raise ValueError("商品中文名不能超过 128 个字符")
    return value


def normalize_shop_item_id(item_id: str) -> str:
    value = str(item_id).strip()
    if not value:
        raise ValueError("物品 ID 不能为空")
    if len(value) > 128:
        raise ValueError("物品 ID 不能超过 128 个字符")
    return value


def normalize_shop_points_cost(points_cost: int) -> int:
    value = normalize_player_points(points_cost)
    if value <= 0:
        raise ValueError("所需积分必须大于 0")
    return value


def normalize_player_points(points: int) -> int:
    value = int(points)
    if value < 0:
        raise ValueError("积分不能为负数")
    if value > MAX_RUST_PLAYER_POINTS:
        raise ValueError(f"积分不能超过 {MAX_RUST_PLAYER_POINTS}")
    return value


def normalize_checkin_points_range(min_points: int, max_points: int) -> tuple[int, int]:
    min_val = normalize_player_points(min_points)
    max_val = normalize_player_points(max_points)
    if min_val > max_val:
        raise ValueError("最小积分不能大于最大积分")
    return min_val, max_val


def normalize_checkin_online_bonus(points: int) -> int:
    return normalize_player_points(points)


def normalize_checkin_rcon_binding_id(binding_id: int) -> int:
    value = int(binding_id)
    if value < 0:
        raise ValueError("RCON 绑定 ID 不能为负数")
    return value


def resolve_checkin_rcon_binding(
    bindings: list[RustRconBindingRecord],
    binding_id: int,
) -> RustRconBindingRecord | None:
    """Return enabled binding for check-in; 0 picks the lowest-id enabled binding."""
    enabled = sorted(
        (binding for binding in bindings if binding.enabled),
        key=lambda binding: binding.id,
    )
    if not enabled:
        return None
    if binding_id == 0:
        return enabled[0]
    for binding in enabled:
        if binding.id == binding_id:
            return binding
    return None
