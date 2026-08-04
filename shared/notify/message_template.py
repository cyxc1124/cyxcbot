"""Template rendering with text and message segment placeholders."""

from __future__ import annotations

import re
from typing import Callable, Iterable, Mapping, Union

from nonebot.adapters.onebot.v11.message import Message, MessageSegment

_PLACEHOLDER = re.compile(r"\{(\w+)\}")

SegmentPart = Union[MessageSegment, str]
SegmentHandler = Callable[[], Iterable[SegmentPart]]


def safe_text(value: str) -> MessageSegment:
    """Build a text segment that will not be re-parsed as CQ code."""
    return MessageSegment.text(value)


def safe_text_message(value: str) -> Message:
    """Build a one-segment Message that will not be re-parsed as CQ code."""
    return Message(safe_text(value))


def render_message_template(template: str, variables: Mapping[str, str]) -> str:
    """Replace `{key}` placeholders in plain text; unknown keys are left unchanged."""

    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in variables:
            return variables[key]
        return match.group(0)

    return _PLACEHOLDER.sub(replacer, template)


def iter_template_parts(template: str) -> Iterable[tuple[str, str]]:
    """Split template into alternating text and `{variable}` parts."""
    pos = 0
    for match in _PLACEHOLDER.finditer(template):
        if match.start() > pos:
            yield ("text", template[pos : match.start()])
        yield ("var", match.group(1))
        pos = match.end()
    if pos < len(template):
        yield ("text", template[pos:])


def _append_part(message: Message, part: SegmentPart) -> None:
    """Append a part; strings become escaped text segments (not CQ-parsed)."""
    if not part:
        return
    if isinstance(part, str):
        message.append(safe_text(part))
    else:
        message.append(part)


def build_message_from_template(
    template: str,
    text_variables: Mapping[str, str],
    segment_handlers: Mapping[str, SegmentHandler] | None = None,
) -> Message:
    """Build a QQ message strictly following template order."""
    message = Message()
    handlers = segment_handlers or {}

    for kind, content in iter_template_parts(template):
        if kind == "text":
            rendered = render_message_template(content, text_variables)
            _append_part(message, rendered)
            continue

        key = content
        if key in handlers:
            for part in handlers[key]() or []:
                _append_part(message, part)
        elif key in text_variables:
            _append_part(message, text_variables[key])
        else:
            _append_part(message, f"{{{key}}}")

    return message
