"""Tests for link-parser user policy list assembly."""

from __future__ import annotations

from admin.services.link_parser_policy_items import build_user_policy_items
from shared.config.link_parser_policy import LinkParserUserPolicyRecord
from shared.config.types import AppConfigSnapshot


def test_build_user_items_empty_when_friend_list_empty_despite_db_policies() -> None:
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


def test_build_user_items_only_includes_provided_friends() -> None:
    snap = AppConfigSnapshot(
        message_private_restrict=True,
        message_enabled_user_ids=["10001", "10002"],
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
