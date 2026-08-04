"""Ensure template/external text is not re-parsed as OneBot CQ codes."""

from __future__ import annotations

from nonebot.adapters.onebot.v11 import MessageSegment

from shared.notify.message_template import (
    build_message_from_template,
    safe_text,
    safe_text_message,
)


def test_build_message_from_template_escapes_cq_in_variables() -> None:
    message = build_message_from_template(
        "标题：{title}\nUP主：{author}",
        {
            "title": "[CQ:at,qq=all] owned",
            "author": "[CQ:image,file=http://127.0.0.1/x]",
        },
    )
    assert all(segment.type == "text" for segment in message)
    serialized = str(message)
    assert "[CQ:at" not in serialized
    assert "&#91;CQ:at,qq=all&#93;" in serialized
    assert "&#91;CQ:image,file=http://127.0.0.1/x&#93;" in serialized


def test_build_message_from_template_escapes_handler_string_parts() -> None:
    message = build_message_from_template(
        "{body}",
        {},
        {
            "body": lambda: [
                "[CQ:at,qq=all]\n",
                MessageSegment.image("http://example/a"),
            ]
        },
    )
    types = [segment.type for segment in message]
    assert types == ["text", "image"]
    assert "&#91;CQ:at,qq=all&#93;" in str(message)


def test_safe_text_message_does_not_parse_cq() -> None:
    message = safe_text_message("prefix [CQ:at,qq=all] suffix")
    assert len(message) == 1
    assert message[0].type == "text"
    assert message[0].data["text"] == "prefix [CQ:at,qq=all] suffix"
    assert str(message) == "prefix &#91;CQ:at,qq=all&#93; suffix"


def test_safe_text_is_message_segment_text() -> None:
    segment = safe_text("[CQ:record,file=1]")
    assert segment.type == "text"
    assert segment.data["text"] == "[CQ:record,file=1]"
