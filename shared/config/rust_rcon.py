"""Rust game server RCON binding records and alias validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict

from shared.config.command_aliases import (
    COMMAND_LABELS,
    CommandAliasEntry,
    resolve_entry,
)

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot

MAX_ALIAS_LENGTH = 32
DEFAULT_RCON_PORT = 28016
MIN_PORT = 1
MAX_PORT = 65535
MAX_ALLOWED_QQ_PER_BINDING = 50


@dataclass(frozen=True)
class RustRconBindingRecord:
    id: int
    alias: str
    host: str
    port: int
    password: str
    enabled: bool = True
    name: str | None = None
    allowed_qq_ids: tuple[str, ...] = ()


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


def normalize_allowed_qq_ids(raw: list[str]) -> list[str]:
    if not raw:
        raise ValueError("请至少填写一个允许执行的 QQ 号")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        qq = str(item).strip()
        if not qq:
            continue
        if not qq.isdigit():
            raise ValueError(f"QQ 号格式无效: {qq}")
        if len(qq) > 32:
            raise ValueError("QQ 号过长")
        if qq in seen:
            continue
        seen.add(qq)
        cleaned.append(qq)
    if not cleaned:
        raise ValueError("请至少填写一个允许执行的 QQ 号")
    if len(cleaned) > MAX_ALLOWED_QQ_PER_BINDING:
        raise ValueError(f"最多允许 {MAX_ALLOWED_QQ_PER_BINDING} 个 QQ 号")
    return cleaned


def is_qq_allowed_for_binding(binding: RustRconBindingRecord, user_id: str) -> bool:
    qq = str(user_id).strip()
    return qq in binding.allowed_qq_ids


def _strip_command_prefix(text: str) -> str | None:
    prefixes: set[str] = {"/"}
    try:
        from nonebot import get_driver

        starts = {str(s) for s in get_driver().config.command_start if s}
        if starts:
            prefixes = starts
    except Exception:
        pass
    try:
        from shared.config.service import get_config_service

        prefixes |= set(get_config_service().get_snapshot().command_extra_prefixes)
    except Exception:
        pass
    for prefix in sorted(prefixes, key=len, reverse=True):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return None


def match_rust_rcon_binding(
    text: str,
    bindings: list[RustRconBindingRecord],
) -> tuple[RustRconBindingRecord, str] | None:
    """Match ``[prefix]alias command``; return (binding, command) or None."""
    enabled = [binding for binding in bindings if binding.enabled]
    if not enabled:
        return None

    text = text.strip()
    candidates = [text]
    stripped = _strip_command_prefix(text)
    if stripped is not None:
        candidates.append(stripped.strip())

    by_alias_len = sorted(enabled, key=lambda binding: len(binding.alias), reverse=True)
    for candidate in candidates:
        for binding in by_alias_len:
            alias = binding.alias
            if candidate == alias:
                return binding, ""
            if (
                candidate.startswith(alias)
                and len(candidate) > len(alias)
                and candidate[len(alias)].isspace()
            ):
                return binding, candidate[len(alias) :].strip()
    return None


def alias_command_conflict(alias: str, snapshot: AppConfigSnapshot) -> str | None:
    """Return error if *alias* matches an enabled built-in command trigger."""
    for command_id in COMMAND_LABELS:
        entry = resolve_entry(command_id, snapshot.command_aliases)
        if entry.enabled and alias in entry.triggers:
            label = COMMAND_LABELS[command_id]
            return f"触发词「{alias}」与命令「{label}」冲突"
    return None


def rust_rcon_command_alias_conflicts(
    config: Dict[str, CommandAliasEntry],
    bindings: list[RustRconBindingRecord],
) -> list[tuple[str, str]]:
    """Return ``[(trigger, command_label), ...]`` for enabled collisions."""
    enabled_aliases = {binding.alias for binding in bindings if binding.enabled}
    if not enabled_aliases:
        return []

    conflicts: list[tuple[str, str]] = []
    for command_id, entry in config.items():
        if not entry.enabled:
            continue
        label = COMMAND_LABELS.get(command_id, command_id)
        for trigger in entry.triggers:
            if trigger in enabled_aliases:
                conflicts.append((trigger, label))
    return conflicts


def warn_rust_rcon_command_alias_conflicts(
    config: Dict[str, CommandAliasEntry],
    bindings: list[RustRconBindingRecord],
) -> None:
    """Log warnings for legacy RCON bindings that collide with command triggers."""
    from nonebot.log import logger

    conflicts = rust_rcon_command_alias_conflicts(config, bindings)
    if not conflicts:
        return
    parts = [
        f"RCON 绑定触发词「{trigger}」与命令「{label}」冲突"
        for trigger, label in conflicts
    ]
    logger.warning(
        "检测到 {} 处 RCON 绑定与命令触发词冲突（{}）；"
        "同一条 @机器人 消息可能同时触发 RCON 与群管命令，"
        "请在 Web Admin 修改 RCON 绑定触发词或相应命令触发词",
        len(conflicts),
        "；".join(parts),
    )


def command_aliases_rust_rcon_conflict(
    config: Dict[str, CommandAliasEntry],
    bindings: list[RustRconBindingRecord],
) -> str | None:
    """Return error if an enabled command trigger collides with an enabled RCON alias."""
    conflicts = rust_rcon_command_alias_conflicts(config, bindings)
    if not conflicts:
        return None
    trigger, label = conflicts[0]
    return f"触发词「{trigger}」与 RCON 绑定冲突（命令「{label}」）"
