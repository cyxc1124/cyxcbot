"""Tests for group special title command parsing."""

from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from shared.group_special_title import (
    MAX_TITLE_LENGTH,
    compose_command_text,
    extract_member_special_title,
    parse_title_command,
    parse_title_from_message,
    title_applied,
    validate_title,
)
from shared.group_special_title_policy import (
    DEFAULT_DAILY_USAGE_LIMIT,
    is_group_special_title_enabled,
    is_group_special_title_enabled_from_snapshot,
)


def test_parse_title_command_slash_and_hash() -> None:
    assert parse_title_command("/头衔 我的头衔") == "我的头衔"
    assert parse_title_command("#头衔 我的头衔") == "我的头衔"
    assert parse_title_command("!头衔 测试") == "测试"


def test_parse_title_command_ignores_unrelated_messages() -> None:
    assert parse_title_command("最新动态") is None
    assert parse_title_command("/头衔") is None
    assert parse_title_command("#头衔") is None


def test_validate_title() -> None:
    assert validate_title("") == "请提供头衔，例如：/头衔 我的头衔"
    assert (
        validate_title("a" * (MAX_TITLE_LENGTH + 1))
        == f"头衔最多 {MAX_TITLE_LENGTH} 个字"
    )
    assert validate_title("我的头衔") is None


def test_default_daily_usage_limit() -> None:
    assert DEFAULT_DAILY_USAGE_LIMIT == 10


def test_group_special_title_policy() -> None:
    class Snap:
        group_special_title_restrict = True
        group_special_title_enabled_group_ids = ["123", "456"]
        group_special_title_daily_limit = 0

    assert is_group_special_title_enabled(
        "123", restrict=True, enabled_group_ids=["123"]
    )
    assert not is_group_special_title_enabled(
        "999", restrict=True, enabled_group_ids=["123"]
    )
    assert is_group_special_title_enabled("999", restrict=False, enabled_group_ids=[])
    assert is_group_special_title_enabled_from_snapshot("456", Snap())
    assert Snap().group_special_title_daily_limit == 0


def test_title_applied() -> None:
    assert title_applied("小草", "小草")
    assert title_applied("小草", " 小草 ")
    assert not title_applied("小草", "小花")
    assert not title_applied("小草", None)


def test_extract_member_special_title() -> None:
    assert extract_member_special_title({"title": "小草"}) == "小草"
    assert extract_member_special_title({"special_title": "小花"}) == "小花"
    assert (
        extract_member_special_title({"title": "小草", "special_title": "小花"})
        == "小花"
    )
    assert extract_member_special_title({}) is None


def test_compose_command_text_keeps_at_display_name() -> None:
    message = Message(
        MessageSegment.text("#头衔 ")
        + MessageSegment("at", {"qq": "1225474798", "name": "🐱神的主任"})
        + MessageSegment.text(" 的主人")
    )
    assert compose_command_text(message) == "#头衔 🐱神的主任 的主人"
    assert parse_title_from_message(message) == "🐱神的主任 的主人"
