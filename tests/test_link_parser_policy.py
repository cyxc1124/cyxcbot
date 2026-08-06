"""Tests for shared.config.link_parser_policy."""

from __future__ import annotations

from shared.config.link_parser_policy import (
    LinkParserGroupPolicyRecord,
    LinkParserScopePolicy,
    LinkParserUserPolicyRecord,
    normalize_link_parser_flags,
    resolve_link_parser_policy,
)
from shared.config.types import AppConfigSnapshot


def _snapshot(**kwargs) -> AppConfigSnapshot:
    return AppConfigSnapshot(**kwargs)


def test_resolve_group_live_only_excludes_dynamic() -> None:
    snap = _snapshot(
        link_parser_group_policies={
            "123": LinkParserGroupPolicyRecord(
                group_id="123",
                video_enabled=False,
                live_enabled=True,
                dynamic_enabled=False,
                send_video_enabled=False,
            )
        }
    )
    scope = resolve_link_parser_policy(snap, group_id="123")
    assert scope == LinkParserScopePolicy(
        video_enabled=False,
        live_enabled=True,
        dynamic_enabled=False,
        send_video_enabled=False,
    )


def test_resolve_user_dynamic_only() -> None:
    snap = _snapshot(
        link_parser_user_policies={
            "456": LinkParserUserPolicyRecord(
                user_id="456",
                dynamic_enabled=True,
            )
        }
    )
    scope = resolve_link_parser_policy(snap, user_id="456", is_private=True)
    assert scope.dynamic_enabled is True
    assert scope.video_enabled is False
    assert scope.live_enabled is False
    assert scope.send_video_enabled is False


def test_resolve_group_send_video_independent() -> None:
    snap = _snapshot(
        link_parser_group_policies={
            "1": LinkParserGroupPolicyRecord(
                group_id="1",
                video_enabled=True,
                send_video_enabled=True,
            )
        }
    )
    scope = resolve_link_parser_policy(snap, group_id="1")
    assert scope.video_enabled is True
    assert scope.send_video_enabled is True


def test_normalize_clears_send_video_when_video_off() -> None:
    video, live, dynamic, send = normalize_link_parser_flags(
        video_enabled=False,
        live_enabled=True,
        dynamic_enabled=False,
        send_video_enabled=True,
    )
    assert (video, live, dynamic, send) == (False, True, False, False)


def test_resolve_ignores_orphan_send_video_flag() -> None:
    snap = _snapshot(
        link_parser_group_policies={
            "1": LinkParserGroupPolicyRecord(
                group_id="1",
                video_enabled=False,
                send_video_enabled=True,
            )
        }
    )
    scope = resolve_link_parser_policy(snap, group_id="1")
    assert scope.video_enabled is False
    assert scope.send_video_enabled is False
