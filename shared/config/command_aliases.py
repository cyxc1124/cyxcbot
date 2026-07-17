"""Configurable trigger words for user-invoked commands (Web Admin: 设置 → 命令).

Each command has a stable ``command_id`` and a full list of trigger words
(seeded from :data:`COMMAND_DEFAULTS`, freely editable/removable by the
admin) plus an ``enabled`` flag. Matching mirrors the conventions already
used by ``dynamic_monitor``/``video_monitor``: bare text, the deployment's
configured ``COMMAND_START`` prefix (see ``env.example``), a few extra
convenience prefixes (默认 ``!``/``。``/``.``/``#``，可在 Web Admin → 设置 →
命令 中自定义), or ``@机器人`` + text. All prefix-aware commands (including
``#提取``/``#头衔`` style ones) share the same :func:`command_prefixes`
resolution, so changing either ``COMMAND_START`` or the convenience prefixes
affects every command consistently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

# 额外“习惯性”前缀的出厂默认值：与 NoneBot 的 COMMAND_START 无关，
# 可在 Web Admin → 设置 → 命令 中自定义（见 normalize_extra_prefixes）。
DEFAULT_EXTRA_PREFIXES = ("!", "。", ".", "#")

MAX_TRIGGER_LENGTH = 32
MAX_TRIGGERS_PER_COMMAND = 20
MAX_EXTRA_PREFIX_LENGTH = 4
MAX_EXTRA_PREFIXES = 10

COMMAND_DEFAULTS: Dict[str, List[str]] = {
    "status": ["status", "状态", "运行状态"],
    "live_status": ["直播状态", "查直播", "live"],
    "live_monitor_list": ["监控列表", "直播监控列表"],
    "dynamic_query_latest": ["最新动态"],
    "dynamic_query_pinned": ["置顶动态"],
    "video_query_latest": ["最新视频", "最新投稿"],
    "dynamic_extract": ["提取", "获取"],
    "group_special_title": ["头衔"],
}

COMMAND_LABELS: Dict[str, str] = {
    "status": "运行状态查询",
    "live_status": "直播状态查询",
    "live_monitor_list": "直播监控列表",
    "dynamic_query_latest": "最新动态查询",
    "dynamic_query_pinned": "置顶动态查询",
    "video_query_latest": "最新投稿查询",
    "dynamic_extract": "动态图片提取",
    "group_special_title": "群头衔设置",
}


@dataclass
class CommandAliasEntry:
    """Resolved trigger config for one command."""

    enabled: bool = True
    triggers: List[str] = field(default_factory=list)


def default_entry(command_id: str) -> CommandAliasEntry:
    return CommandAliasEntry(
        enabled=True, triggers=list(COMMAND_DEFAULTS.get(command_id, []))
    )


def default_config() -> Dict[str, CommandAliasEntry]:
    return {command_id: default_entry(command_id) for command_id in COMMAND_DEFAULTS}


def _clean_triggers(raw: object) -> List[str]:
    if not isinstance(raw, list):
        return []
    cleaned: List[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip()
        if not text or len(text) > MAX_TRIGGER_LENGTH or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
        if len(cleaned) >= MAX_TRIGGERS_PER_COMMAND:
            break
    return cleaned


def normalize_extra_prefixes(raw: object) -> List[str]:
    """Clean/dedup a persisted/API prefix list; malformed input yields ``[]``.

    Unlike triggers, an explicitly empty list is a valid choice (no
    convenience prefixes) and is *not* coerced back to
    :data:`DEFAULT_EXTRA_PREFIXES` — callers seed a fresh DB with the
    defaults so "never configured" and "explicitly emptied" stay distinct.
    """
    if not isinstance(raw, list):
        return []
    cleaned: List[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip()
        if not text or len(text) > MAX_EXTRA_PREFIX_LENGTH or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
        if len(cleaned) >= MAX_EXTRA_PREFIXES:
            break
    return cleaned


def normalize_command_aliases(raw: object) -> Dict[str, CommandAliasEntry]:
    """Parse persisted/API JSON into a full mapping covering every known command.

    Unknown ids are dropped; missing/malformed ids fall back to defaults.
    """
    data = raw if isinstance(raw, dict) else {}
    result: Dict[str, CommandAliasEntry] = {}
    for command_id in COMMAND_DEFAULTS:
        entry_raw = data.get(command_id)
        if isinstance(entry_raw, dict):
            enabled = bool(entry_raw.get("enabled", True))
            triggers = _clean_triggers(entry_raw.get("triggers"))
            result[command_id] = CommandAliasEntry(enabled=enabled, triggers=triggers)
        else:
            result[command_id] = default_entry(command_id)
    return result


def serialize_command_aliases(config: Dict[str, CommandAliasEntry]) -> dict:
    """Plain-dict form for JSON storage / API responses."""
    return {
        command_id: {"enabled": entry.enabled, "triggers": list(entry.triggers)}
        for command_id, entry in config.items()
    }


def find_trigger_conflicts(
    config: Dict[str, CommandAliasEntry],
) -> Dict[str, List[str]]:
    """Return ``{trigger: [command_id, ...]}`` for triggers shared by 2+ commands."""
    seen: Dict[str, List[str]] = {}
    for command_id, entry in config.items():
        for trigger in entry.triggers:
            seen.setdefault(trigger, []).append(command_id)
    return {trigger: ids for trigger, ids in seen.items() if len(ids) > 1}


def validation_error(config: Dict[str, CommandAliasEntry]) -> str | None:
    """Return a Chinese error message if *config* is invalid to persist, else None."""
    for command_id, entry in config.items():
        if entry.enabled and not entry.triggers:
            label = COMMAND_LABELS.get(command_id, command_id)
            return f"「{label}」已启用但未配置触发词"

    conflicts = find_trigger_conflicts(config)
    if conflicts:
        parts = [
            f"{trigger}（{'、'.join(COMMAND_LABELS.get(cid, cid) for cid in ids)}）"
            for trigger, ids in conflicts.items()
        ]
        return f"触发词冲突: {'; '.join(parts)}"

    return None


def resolve_entry(
    command_id: str, config: Dict[str, CommandAliasEntry]
) -> CommandAliasEntry:
    return config.get(command_id) or default_entry(command_id)


def trigger_alternation(
    command_id: str, config: Dict[str, CommandAliasEntry]
) -> str | None:
    """Regex-escaped ``a|b|c`` alternation of enabled triggers, or None if disabled/empty."""
    entry = resolve_entry(command_id, config)
    if not entry.enabled or not entry.triggers:
        return None
    return "|".join(re.escape(t) for t in sorted(entry.triggers, key=len, reverse=True))


def _configured_command_starts() -> frozenset[str]:
    """NoneBot's ``COMMAND_START`` (fixed at process startup; see ``env.example``)."""
    try:
        from nonebot import get_driver

        starts = {str(s) for s in get_driver().config.command_start if s}
    except Exception:
        starts = set()
    return frozenset(starts) if starts else frozenset({"/"})


def _extra_prefixes() -> frozenset[str]:
    """习惯性前缀：默认见 :data:`DEFAULT_EXTRA_PREFIXES`，可在 Web Admin → 设置 →
    命令 中自定义（存于 DB，热更新，与 COMMAND_START 无关）。"""
    from shared.config.service import get_config_service

    return frozenset(get_config_service().get_snapshot().command_extra_prefixes)


def command_prefixes() -> frozenset[str]:
    """Prefixes accepted before a trigger word: configured ``COMMAND_START`` plus
    the configurable convenience prefixes."""
    return _configured_command_starts() | _extra_prefixes()


def prefix_alternation() -> str:
    """Regex-escaped ``a|b|c`` alternation of :func:`command_prefixes`, longest first.

    For commands (``dynamic_extract``/``group_special_title``) that embed the
    prefix directly into a larger custom regex instead of using
    :func:`match_plain`/:func:`match_command_arg`.
    """
    return "|".join(
        re.escape(p) for p in sorted(command_prefixes(), key=len, reverse=True)
    )


def _strip_command_prefix(text: str) -> str | None:
    for prefix in sorted(command_prefixes(), key=len, reverse=True):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return None


def match_plain(
    text: str,
    command_id: str,
    config: Dict[str, CommandAliasEntry],
    *,
    is_tome: bool = False,
) -> bool:
    """Whole-message trigger match: bare text, prefixed text, or ``@机器人`` mention."""
    entry = resolve_entry(command_id, config)
    if not entry.enabled or not entry.triggers:
        return False
    text = text.strip()
    if is_tome:
        if text in entry.triggers:
            return True
        return any(text.startswith(t) or text.endswith(t) for t in entry.triggers)
    stripped = _strip_command_prefix(text)
    if stripped is not None:
        return stripped.strip() in entry.triggers
    return text in entry.triggers


def match_command_arg(
    text: str,
    command_id: str,
    config: Dict[str, CommandAliasEntry],
) -> str | None:
    """Match ``[prefix]trigger[ arg]``; return the trailing arg text, or None if unmatched."""
    entry = resolve_entry(command_id, config)
    if not entry.enabled or not entry.triggers:
        return None
    text = text.strip()
    candidates = [text]
    stripped = _strip_command_prefix(text)
    if stripped is not None:
        candidates.append(stripped.strip())
    for candidate in candidates:
        for trigger in sorted(entry.triggers, key=len, reverse=True):
            if candidate == trigger:
                return ""
            if candidate.startswith(trigger) and candidate[len(trigger)].isspace():
                return candidate[len(trigger) :].strip()
    return None
