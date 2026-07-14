"""Build Web Admin link-parser policy list rows from live OneBot data."""

from __future__ import annotations

from typing import Literal

from admin.schemas.link_parser import LinkParserUserPolicyItem
from shared.private_policy import is_private_message_enabled_from_snapshot


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


def build_user_policy_items(
    snap,
    users: list[dict],
    *,
    include_configured_non_friends: bool = False,
) -> list[LinkParserUserPolicyItem]:
    """Map live friend rows; optionally keep DB policies for non-friend QQ IDs.

    *include_configured_non_friends* should only be true after a *complete* friend-list
    fetch. Offline/incomplete callers must leave it false so DB-only rows are not
    treated as a substitute for a missing list.
    """
    by_id: dict[str, dict] = {str(user["user_id"]): user for user in users}

    if include_configured_non_friends:
        for user_id, record in snap.link_parser_user_policies.items():
            if user_id in by_id:
                continue
            if not is_private_message_enabled_from_snapshot(user_id, snap):
                continue
            by_id[user_id] = {"user_id": user_id, "nickname": record.name}

    return [
        build_user_policy_item(snap, by_id[user_id])
        for user_id in sorted(
            by_id.keys(), key=lambda value: (not value.isdigit(), value)
        )
    ]


def friend_list_listing_mode(
    status: Literal["ok", "offline", "incomplete"],
) -> Literal["map", "empty", "error"]:
    """How the admin user-policy list should treat a friend-list fetch.

    - map: complete live list, safe to render (may also show configured non-friends)
    - empty: no bots connected → show empty state (not DB orphans)
    - error: bots connected but fetch incomplete → fail the request (do not
      fall back to DB rows or silently show a partial list)
    """
    if status == "ok":
        return "map"
    if status == "incomplete":
        return "error"
    return "empty"
