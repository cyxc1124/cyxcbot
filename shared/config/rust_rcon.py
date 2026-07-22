"""Rust game server RCON binding records and alias validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from shared.config.command_aliases import COMMAND_LABELS, resolve_entry

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot

MAX_ALIAS_LENGTH = 32
DEFAULT_RCON_PORT = 28016
MIN_PORT = 1
MAX_PORT = 65535


@dataclass(frozen=True)
class RustRconBindingRecord:
    id: int
    alias: str
    host: str
    port: int
    password: str
    enabled: bool = True
    name: str | None = None


def normalize_alias(raw: str) -> str:
    alias = str(raw).strip()
    if not alias:
        raise ValueError("触发词不能为空")
    if len(alias) > MAX_ALIAS_LENGTH:
        raise ValueError(f"触发词长度不能超过 {MAX_ALIAS_LENGTH} 个字符")
    if any(ch.isspace() for ch in alias):
        raise ValueError("触发词不能包含空白字符")
    return alias


def normalize_port(raw: int) -> int:
    port = int(raw)
    if port < MIN_PORT or port > MAX_PORT:
        raise ValueError(f"端口必须在 {MIN_PORT}–{MAX_PORT} 之间")
    return port


def alias_command_conflict(alias: str, snapshot: AppConfigSnapshot) -> str | None:
    """Return error if *alias* matches an enabled built-in command trigger."""
    for command_id in COMMAND_LABELS:
        entry = resolve_entry(command_id, snapshot.command_aliases)
        if entry.enabled and alias in entry.triggers:
            label = COMMAND_LABELS[command_id]
            return f"触发词「{alias}」与命令「{label}」冲突"
    return None
