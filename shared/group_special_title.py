"""Parse and validate group special title commands."""

from __future__ import annotations

import re

from nonebot.adapters.onebot.v11.message import Message

MAX_TITLE_LENGTH = 6

TITLE_COMMAND_PATTERN = re.compile(
    r"^(?:#头衔|[/!。.]头衔)\s+(.+)$",
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


def parse_title_command(message_text: str) -> str | None:
    """Return title from ``/头衔 …`` or ``#头衔 …``, or None if not matched."""
    match = TITLE_COMMAND_PATTERN.match(message_text.strip())
    if not match:
        return None
    return match.group(1).strip()


def parse_title_from_message(message: Message) -> str | None:
    """Parse title command from a group message, including ``@`` display names."""
    return parse_title_command(compose_command_text(message))


def validate_title(title: str) -> str | None:
    """Return an error message when *title* is invalid, else None."""
    if not title:
        return "请提供头衔，例如：/头衔 我的头衔"
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
