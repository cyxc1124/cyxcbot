"""Tests for private status whitelist visibility filtering."""

from shared.private_policy import filter_enabled_user_ids_to_visible_users


def test_filter_preserves_ids_when_friend_list_unavailable() -> None:
    assert filter_enabled_user_ids_to_visible_users(
        ["10001", "10002"],
        [],
        friend_list_available=False,
    ) == ["10001", "10002"]


def test_filter_clears_ids_when_no_visible_friends_but_list_available() -> None:
    assert (
        filter_enabled_user_ids_to_visible_users(
            ["10001", "10002"],
            [],
            friend_list_available=True,
        )
        == []
    )


def test_filter_removes_unknown_users() -> None:
    users = [{"user_id": "10001", "nickname": "a"}]
    assert filter_enabled_user_ids_to_visible_users(["10001", "10002"], users) == [
        "10001"
    ]
