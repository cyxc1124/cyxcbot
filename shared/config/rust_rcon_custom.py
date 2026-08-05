"""Rust RCON custom command templates and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from shared.config.command_aliases import COMMAND_LABELS, resolve_entry
from shared.config.rust_player import normalize_steam_id
from shared.config.rust_rcon import MAX_ALIAS_LENGTH, normalize_alias

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot

STEAMID_PLACEHOLDER = "{steamid}"
MAX_TEMPLATE_LENGTH = 512


@dataclass(frozen=True)
class RustRconCustomCommandRecord:
    id: int
    name: str
    template: str
    binding_id: int
    enabled: bool = True


def normalize_custom_command_name(raw: str) -> str:
    # Reuse RCON alias rules: non-empty, no whitespace, max length.
    return normalize_alias(raw)


def normalize_custom_command_template(raw: str) -> str:
    template = str(raw).strip()
    if not template:
        raise ValueError("命令模板不能为空")
    if len(template) > MAX_TEMPLATE_LENGTH:
        raise ValueError(f"命令模板长度不能超过 {MAX_TEMPLATE_LENGTH} 个字符")
    return template


def template_needs_steamid(template: str) -> bool:
    return STEAMID_PLACEHOLDER in template


def render_custom_command_template(template: str, steam_id: str | None) -> str:
    if not template_needs_steamid(template):
        return template
    if not steam_id:
        raise ValueError("该指令需要 SteamID")
    return template.replace(STEAMID_PLACEHOLDER, steam_id)


def _strip_command_prefix(text: str) -> str | None:
    from shared.config.rust_rcon import _strip_command_prefix as strip_prefix

    return strip_prefix(text)


def match_rust_rcon_custom_command(
    text: str,
    commands: list[RustRconCustomCommandRecord],
    *,
    enabled_binding_ids: set[int] | None = None,
) -> tuple[RustRconCustomCommandRecord, str] | None:
    """Match ``[prefix]name [args]``; return (command, remainder) or None."""
    enabled = [
        command
        for command in commands
        if command.enabled
        and (enabled_binding_ids is None or command.binding_id in enabled_binding_ids)
    ]
    if not enabled:
        return None

    text = text.strip()
    candidates = [text]
    stripped = _strip_command_prefix(text)
    if stripped is not None:
        candidates.append(stripped.strip())

    by_name_len = sorted(enabled, key=lambda command: len(command.name), reverse=True)
    for candidate in candidates:
        for command in by_name_len:
            name = command.name
            if candidate == name:
                return command, ""
            if (
                candidate.startswith(name)
                and len(candidate) > len(name)
                and candidate[len(name)].isspace()
            ):
                return command, candidate[len(name) :].strip()
    return None


def resolve_steamid_target(
    remainder: str,
    mentioned_user_ids: list[str],
) -> tuple[str | None, str | None]:
    """Return ``(kind, value)`` where kind is ``qq`` / ``steamid``, or ``(None, None)``.

    Prefer @mention over plaintext SteamID when both are present.
    """
    if mentioned_user_ids:
        return "qq", mentioned_user_ids[0]

    token = remainder.strip().split(None, 1)[0] if remainder.strip() else ""
    if not token:
        return None, None
    steam_id = normalize_steam_id(token)
    if steam_id is not None:
        return "steamid", steam_id
    if token.isdigit() or token.lower().startswith("7656"):
        return "invalid_steamid", token
    return None, None


def custom_command_name_conflict(
    name: str,
    snapshot: AppConfigSnapshot,
    *,
    exclude_id: int | None = None,
) -> str | None:
    """Return error if *name* collides with aliases / other custom commands."""
    for command_id in COMMAND_LABELS:
        entry = resolve_entry(command_id, snapshot.command_aliases)
        if entry.enabled and name in entry.triggers:
            label = COMMAND_LABELS[command_id]
            return f"指令名「{name}」与命令「{label}」冲突"

    for binding in snapshot.rust_rcon_bindings:
        if binding.enabled and binding.alias == name:
            return f"指令名「{name}」与 RCON 绑定触发词冲突"

    for command in snapshot.rust_rcon_custom_commands:
        if command.name == name and command.id != exclude_id:
            return f"指令名「{name}」已存在"

    return None


def alias_custom_command_conflict(
    alias: str,
    commands: list[RustRconCustomCommandRecord],
) -> str | None:
    for command in commands:
        if command.enabled and command.name == alias:
            return f"触发词「{alias}」与自定义指令「{command.name}」冲突"
    return None


def command_aliases_custom_command_conflict(
    config: dict,
    commands: list[RustRconCustomCommandRecord],
) -> str | None:
    enabled_names = {command.name for command in commands if command.enabled}
    if not enabled_names:
        return None
    for command_id, entry in config.items():
        if not getattr(entry, "enabled", False):
            continue
        label = COMMAND_LABELS.get(command_id, command_id)
        for trigger in entry.triggers:
            if trigger in enabled_names:
                return f"触发词「{trigger}」与自定义指令冲突（命令「{label}」）"
    return None


# Re-export for callers that validate name length against the shared constant.
MAX_CUSTOM_COMMAND_NAME_LENGTH = MAX_ALIAS_LENGTH
