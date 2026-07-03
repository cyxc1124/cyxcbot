"""Tests for group special title command parsing."""

from shared.group_special_title import (
    DAILY_USAGE_LIMIT,
    MAX_TITLE_LENGTH,
    parse_title_command,
    validate_title,
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


def test_daily_usage_limit_is_three() -> None:
    assert DAILY_USAGE_LIMIT == 3
