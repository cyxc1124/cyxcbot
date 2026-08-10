"""Tests for X link-parser policy resolution."""

from __future__ import annotations

from shared.config.types import AppConfigSnapshot
from shared.config.x_link_parser_policy import (
    XLinkParserGroupPolicyRecord,
    XLinkParserUserPolicyRecord,
    resolve_x_link_parser_policy,
)


def test_default_disabled():
    snap = AppConfigSnapshot()
    assert not resolve_x_link_parser_policy(
        snap, group_id="1", is_private=False
    ).enabled
    assert not resolve_x_link_parser_policy(snap, user_id="2", is_private=True).enabled


def test_group_override():
    snap = AppConfigSnapshot(
        x_link_parser_group_policies={
            "100": XLinkParserGroupPolicyRecord(group_id="100", enabled=True)
        }
    )
    assert resolve_x_link_parser_policy(snap, group_id="100", is_private=False).enabled
    assert not resolve_x_link_parser_policy(
        snap, group_id="101", is_private=False
    ).enabled


def test_user_override_private():
    snap = AppConfigSnapshot(
        x_link_parser_user_policies={
            "200": XLinkParserUserPolicyRecord(user_id="200", enabled=True)
        }
    )
    assert resolve_x_link_parser_policy(snap, user_id="200", is_private=True).enabled
    assert not resolve_x_link_parser_policy(
        snap, user_id="201", is_private=True
    ).enabled
