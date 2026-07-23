"""Parse Rust server ``give`` RCON responses."""

from __future__ import annotations

import re

# Substrings from Rust console (case-insensitive match).
_GIVE_FAILURE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("couldn't find player", "玩家不在线"),
    ("invalid item", "物品 ID 无效"),
    ("inventory full", "背包已满"),
)

_QUANTITY_TOKEN_RE = re.compile(r"^\d+$")


def normalize_give_quantity(quantity: int) -> int:
    """Validate give amount: non-negative integer, not a decimal."""
    if isinstance(quantity, bool):
        raise ValueError("物品数量格式无效")
    if isinstance(quantity, float) and not quantity.is_integer():
        raise ValueError("物品数量不能为小数")
    value = int(quantity)
    if value < 0:
        raise ValueError("物品数量不能为负数")
    return value


def parse_quantity_token(raw: str) -> int | None:
    """Return a non-negative int quantity token, or None if not a plain integer."""
    token = str(raw).strip()
    if not _QUANTITY_TOKEN_RE.fullmatch(token):
        return None
    return int(token)


def parse_give_rejection(response: str) -> str | None:
    """Return user-facing failure reason when give was rejected, else None."""
    text = (response or "").strip()
    if not text:
        return None
    lowered = text.lower()
    for needle, message in _GIVE_FAILURE_PATTERNS:
        if needle in lowered:
            return message
    return None
