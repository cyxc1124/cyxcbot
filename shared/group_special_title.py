"""Parse and validate group special title commands."""

from __future__ import annotations

import re

from nonebot.adapters.onebot.v11.message import Message

from shared.config.command_aliases import (
    CommandAliasEntry,
    prefix_alternation,
    trigger_alternation,
)

MAX_TITLE_LENGTH = 6


def _build_title_pattern(
    command_aliases: dict[str, CommandAliasEntry],
    *,
    prefixes: frozenset[str] | None = None,
) -> re.Pattern[str] | None:
    """Build the ``{prefix}{触发词} …`` pattern from configured trigger words."""
    alternation = trigger_alternation("group_special_title", command_aliases)
    if alternation is None:
        return None
    return re.compile(
        rf"^(?:{prefix_alternation(prefixes)})(?P<trigger>{alternation})\s+(?P<title>.+)$"
    )


def compose_command_text(message: Message) -> str:
    """Rebuild command text from segments so ``@`` display names are kept."""
    parts: list[str] = []
    for segment in message:
        if segment.type == "text":
            parts.append(str(segment.data.get("text", "")))
        elif segment.type == "at":
            name = segment.data.get("name")
            if name:
                parts.append(str(name))
            else:
                qq = segment.data.get("qq")
                if qq:
                    parts.append(f"@{qq}")
    return "".join(parts).strip()


def _match_title_command(
    message_text: str,
    command_aliases: dict[str, CommandAliasEntry] | None = None,
    *,
    prefixes: frozenset[str] | None = None,
) -> tuple[str, str] | None:
    """Return the actual trigger and title from the complete command."""
    pattern = _build_title_pattern(command_aliases or {}, prefixes=prefixes)
    if pattern is None:
        return None
    match = pattern.match(message_text.strip())
    if not match:
        return None
    return match.group("trigger"), match.group("title").strip()


def parse_title_command(
    message_text: str,
    command_aliases: dict[str, CommandAliasEntry] | None = None,
    *,
    prefixes: frozenset[str] | None = None,
) -> str | None:
    """Return title from ``{prefix}{触发词} …``, or None if not matched."""
    command = _match_title_command(message_text, command_aliases, prefixes=prefixes)
    return command[1] if command else None


def parse_title_from_message(
    message: Message,
    command_aliases: dict[str, CommandAliasEntry] | None = None,
) -> str | None:
    """Parse title command from a group message, including ``@`` display names."""
    return parse_title_command(compose_command_text(message), command_aliases)


def validate_title(title: str) -> str | None:
    """Return an error message when *title* is invalid, else None."""
    if not title:
        return "请提供头衔内容"
    if len(title) > MAX_TITLE_LENGTH:
        return f"头衔最多 {MAX_TITLE_LENGTH} 个字"
    return None


def title_applied(expected: str, actual: str | None) -> bool:
    """Return whether *actual* matches the requested special title."""
    return (actual or "").strip() == expected.strip()


def extract_member_special_title(member_info: dict) -> str | None:
    """Read special title from OneBot member info (LLBot uses ``title``)."""
    for key in ("special_title", "title"):
        value = member_info.get(key)
        if isinstance(value, str):
            return value
    return None
