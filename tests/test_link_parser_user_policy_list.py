"""Tests for link-parser user policy list assembly."""

from __future__ import annotations

from admin.services.link_parser_policy_items import (
    build_user_policy_items,
    onebot_list_listing_mode,
)
from shared.config.link_parser_policy import LinkParserUserPolicyRecord
from shared.config.types import AppConfigSnapshot


def test_build_user_items_empty_when_friend_list_empty_despite_db_policies() -> None:
    """Offline/incomplete callers must not resurrect DB rows by default."""
    snap = AppConfigSnapshot(
        message_private_restrict=True,
        message_enabled_user_ids=["10001"],
        link_parser_user_policies={
            "10001": LinkParserUserPolicyRecord(
                user_id="10001",
                video_enabled=True,
                name="cached",
            )
        },
    )

    assert build_user_policy_items(snap, []) == []


def test_build_user_items_only_includes_provided_friends_by_default() -> None:
    snap = AppConfigSnapshot(
        message_private_restrict=True,
        message_enabled_user_ids=["10001", "10002", "99999"],
        link_parser_user_policies={
            "10001": LinkParserUserPolicyRecord(
                user_id="10001",
                live_enabled=True,
                name="alice",
            ),
            "99999": LinkParserUserPolicyRecord(
                user_id="99999",
                dynamic_enabled=True,
                name="orphan",
            ),
        },
    )
    friends = [{"user_id": "10001", "nickname": "Alice"}]

    items = build_user_policy_items(snap, friends)

    assert len(items) == 1
    assert items[0].user_id == "10001"
    assert items[0].nickname == "Alice"
    assert items[0].live_enabled is True
    assert items[0].customized is True


def test_build_user_items_preserves_configured_non_friends_after_complete_fetch() -> (
    None
):
    snap = AppConfigSnapshot(
        message_private_restrict=True,
        message_enabled_user_ids=["10001", "99999"],
        link_parser_user_policies={
            "10001": LinkParserUserPolicyRecord(
                user_id="10001",
                live_enabled=True,
                name="alice",
            ),
            "99999": LinkParserUserPolicyRecord(
                user_id="99999",
                dynamic_enabled=True,
                name="orphan",
            ),
            "88888": LinkParserUserPolicyRecord(
                user_id="88888",
                video_enabled=True,
                name="disabled-msg",
            ),
        },
    )
    friends = [{"user_id": "10001", "nickname": "Alice"}]

    items = build_user_policy_items(
        snap,
        friends,
        include_configured_non_friends=True,
    )

    assert [item.user_id for item in items] == ["10001", "99999"]
    assert items[1].nickname == "orphan"
    assert items[1].dynamic_enabled is True
    assert items[1].customized is True


def test_onebot_list_listing_mode_distinguishes_offline_and_incomplete() -> None:
    assert onebot_list_listing_mode("ok") == "map"
    assert onebot_list_listing_mode("offline") == "empty"
    assert onebot_list_listing_mode("incomplete") == "partial"
