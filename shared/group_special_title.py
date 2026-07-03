"""Parse and validate group special title commands."""

from __future__ import annotations

import re

MAX_TITLE_LENGTH = 6
DAILY_USAGE_LIMIT = 3

TITLE_COMMAND_PATTERN = re.compile(
    r"^(?:#头衔|[/!。.]头衔)\s+(.+)$",
)


def parse_title_command(message_text: str) -> str | None:
    """Return title from ``/头衔 …`` or ``#头衔 …``, or None if not matched."""
    match = TITLE_COMMAND_PATTERN.match(message_text.strip())
    if not match:
        return None
    return match.group(1).strip()


def validate_title(title: str) -> str | None:
    """Return an error message when *title* is invalid, else None."""
    if not title:
        return "请提供头衔，例如：/头衔 我的头衔"
    if len(title) > MAX_TITLE_LENGTH:
        return f"头衔最多 {MAX_TITLE_LENGTH} 个字"
    return None
