"""Rust RCON custom command templates and matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from shared.config.command_aliases import COMMAND_LABELS, match_plain
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
    allowed_qq_ids: tuple[str, ...] = ()


def is_qq_allowed_for_custom_command(
    command: RustRconCustomCommandRecord, user_id: str
) -> bool:
    qq = str(user_id).strip()
    return qq in command.allowed_qq_ids


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


def trigger_match_keys(trigger: str) -> set[str]:
    """Forms a trigger can match after the same prefix stripping as runtime matchers."""
    trigger = str(trigger).strip()
    if not trigger:
        return set()
    keys = {trigger}
    stripped = _strip_command_prefix(trigger)
    if stripped is not None:
        stripped = stripped.strip()
        if stripped:
            keys.add(stripped)
    return keys


def triggers_conflict(left: str, right: str) -> bool:
    return bool(trigger_match_keys(left) & trigger_match_keys(right))


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


def collect_explicit_mention_qq_ids(
    segments: list[tuple[str, str]],
    *,
    self_id: str,
) -> list[str]:
    """Return distinct @QQ targets from ``(type, qq)`` segments.

    Skips ``at`` that immediately follows a ``reply`` segment — QQ clients
    commonly inject that auto-@ when replying, and it must not become the
    RCON target.
    """
    self_id = str(self_id).strip()
    result: list[str] = []
    for index, (segment_type, raw_qq) in enumerate(segments):
        if segment_type != "at":
            continue
        if index > 0 and segments[index - 1][0] == "reply":
            continue
        qq = str(raw_qq).strip()
        if not qq or qq == "all" or qq == self_id:
            continue
        if qq not in result:
            result.append(qq)
    return result


def resolve_steamid_target(
    remainder: str,
    mentioned_user_ids: list[str],
) -> tuple[str | None, str | None]:
    """Return ``(kind, value)`` where kind is ``qq`` / ``steamid``, or ``(None, None)``.

    Explicit SteamID64 in the remainder wins over @mentions (QQ reply often
    injects an ``at`` for the replied user that is not the intended RCON
    target). Multiple distinct @mentions are rejected as ambiguous.
    """
    if len(mentioned_user_ids) > 1:
        return "ambiguous_mention", None

    token = remainder.strip().split(None, 1)[0] if remainder.strip() else ""
    steam_id = normalize_steam_id(token) if token else None
    if steam_id is not None:
        return "steamid", steam_id
    if token and (token.isdigit() or token.lower().startswith("7656")):
        return "invalid_steamid", token

    if mentioned_user_ids:
        return "qq", mentioned_user_ids[0]
    return None, None


def custom_command_name_conflict(
    name: str,
    snapshot: AppConfigSnapshot,
    *,
    exclude_id: int | None = None,
) -> str | None:
    """Return error if *name* collides with aliases / other custom commands.

    Built-in command checks use the same ``@机器人`` fuzzy prefix/suffix
    semantics as runtime ``match_plain(..., is_tome=True)``, so names like
    ``签到奖励`` conflict with trigger ``签到``.
    """
    for command_id in COMMAND_LABELS:
        if match_plain(name, command_id, snapshot.command_aliases, is_tome=True):
            label = COMMAND_LABELS[command_id]
            return f"指令名「{name}」与命令「{label}」冲突"

    for binding in snapshot.rust_rcon_bindings:
        if binding.enabled and triggers_conflict(binding.alias, name):
            return f"指令名「{name}」与 RCON 绑定触发词冲突"

    for command in snapshot.rust_rcon_custom_commands:
        if command.id != exclude_id and triggers_conflict(command.name, name):
            return f"指令名「{name}」已存在"

    return None


def alias_custom_command_conflict(
    alias: str,
    commands: list[RustRconCustomCommandRecord],
) -> str | None:
    for command in commands:
        if command.enabled and triggers_conflict(command.name, alias):
            return f"触发词「{alias}」与自定义指令「{command.name}」冲突"
    return None


def command_aliases_custom_command_conflict(
    config: dict,
    commands: list[RustRconCustomCommandRecord],
) -> str | None:
    enabled_commands = [command for command in commands if command.enabled]
    if not enabled_commands:
        return None
    for command_id, entry in config.items():
        if not getattr(entry, "enabled", False):
            continue
        label = COMMAND_LABELS.get(command_id, command_id)
        for command in enabled_commands:
            if match_plain(command.name, command_id, config, is_tome=True):
                return f"触发词与自定义指令「{command.name}」冲突（命令「{label}」）"
    return None


# Re-export for callers that validate name length against the shared constant.
MAX_CUSTOM_COMMAND_NAME_LENGTH = MAX_ALIAS_LENGTH
