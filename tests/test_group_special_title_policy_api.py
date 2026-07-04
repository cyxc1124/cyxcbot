"""Tests for group special title policy helpers."""

from shared.group_special_title_policy import filter_enabled_group_ids_to_visible_groups


def test_filter_preserves_ids_when_group_list_empty() -> None:
    assert filter_enabled_group_ids_to_visible_groups(["123", "456"], []) == [
        "123",
        "456",
    ]


def test_filter_removes_unknown_groups() -> None:
    groups = [{"group_id": "123", "group_name": "test", "member_count": 1}]
    assert filter_enabled_group_ids_to_visible_groups(["123", "456"], groups) == [
        "123"
    ]
