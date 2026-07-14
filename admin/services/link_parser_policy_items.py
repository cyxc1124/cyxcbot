"""Build Web Admin link-parser policy list rows from live OneBot data."""

from __future__ import annotations

from typing import Literal

from admin.schemas.link_parser import LinkParserUserPolicyItem


def _user_policy_values(snap, user_id: str) -> tuple[bool, bool, bool, bool]:
    override = snap.link_parser_user_policies.get(str(user_id).strip())
    if override:
        return (
            override.video_enabled,
            override.live_enabled,
            override.dynamic_enabled,
            True,
        )
    return False, False, False, False


def build_user_policy_item(snap, user: dict) -> LinkParserUserPolicyItem:
    user_id = str(user["user_id"])
    video_enabled, live_enabled, dynamic_enabled, customized = _user_policy_values(
        snap, user_id
    )
    override = snap.link_parser_user_policies.get(user_id)
    return LinkParserUserPolicyItem(
        user_id=user_id,
        nickname=user.get("nickname"),
        name=override.name if override else None,
        customized=customized,
        video_enabled=video_enabled,
        live_enabled=live_enabled,
        dynamic_enabled=dynamic_enabled,
    )


def build_user_policy_items(snap, users: list[dict]) -> list[LinkParserUserPolicyItem]:
    """Map live friend rows only; do not resurrect DB-only orphan policies."""
    return [build_user_policy_item(snap, user) for user in users]


def friend_list_listing_mode(
    status: Literal["ok", "offline", "incomplete"],
) -> Literal["map", "empty", "error"]:
    """How the admin user-policy list should treat a friend-list fetch.

    - map: complete live list, safe to render
    - empty: no bots connected → show empty state (not DB orphans)
    - error: bots connected but fetch incomplete → fail the request (do not
      fall back to DB rows or silently show a partial list)
    """
    if status == "ok":
        return "map"
    if status == "incomplete":
        return "error"
    return "empty"

