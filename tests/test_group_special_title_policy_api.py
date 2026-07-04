"""Tests for group special title policy helpers."""

from shared.group_special_title_policy import (
    filter_enabled_group_ids_to_visible_groups,
    special_title_policy_group_list_available,
    special_title_relevant_group_ids,
)


class _Snap:
    group_special_title_restrict = True
    group_special_title_enabled_group_ids = ["123", "999"]
    message_group_restrict = True
    message_enabled_group_ids = ["123", "999"]


def test_filter_preserves_ids_when_group_list_unavailable() -> None:
    assert filter_enabled_group_ids_to_visible_groups(
        ["123", "456"],
        [],
        group_list_available=False,
    ) == ["123", "456"]


def test_filter_clears_ids_when_no_visible_groups_but_list_available() -> None:
    assert (
        filter_enabled_group_ids_to_visible_groups(
            ["123", "456"],
            [],
            group_list_available=True,
        )
        == []
    )


def test_filter_removes_unknown_groups() -> None:
    groups = [{"group_id": "123", "group_name": "test", "member_count": 1}]
    assert filter_enabled_group_ids_to_visible_groups(["123", "456"], groups) == ["123"]


def test_relevant_group_ids_respects_title_whitelist() -> None:
    assert special_title_relevant_group_ids(_Snap()) == ["123", "999"]


def test_policy_unavailable_when_whitelisted_group_missing_from_fetch() -> None:
    snap = _Snap()
    raw_groups = [{"group_id": "123", "group_name": "a", "member_count": 1}]
    assert special_title_policy_group_list_available(True, raw_groups, snap) is False


def test_policy_available_when_all_whitelisted_groups_fetched() -> None:
    snap = _Snap()
    raw_groups = [
        {"group_id": "123", "group_name": "a", "member_count": 1},
        {"group_id": "999", "group_name": "b", "member_count": 2},
    ]
    assert special_title_policy_group_list_available(True, raw_groups, snap) is True
