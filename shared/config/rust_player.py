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
