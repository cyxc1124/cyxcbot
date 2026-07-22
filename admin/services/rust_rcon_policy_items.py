"""Build Web Admin Rust RCON policy list rows from live OneBot data."""

from __future__ import annotations

from typing import Literal

from admin.schemas.rust_rcon_policy import (
    RustRconGroupPolicyItem,
    RustRconUserPolicyItem,
)
from shared.private_policy import is_private_message_enabled_from_snapshot


def _group_policy_values(snap, group_id: str) -> tuple[bool, bool]:
    override = snap.rust_rcon_group_policies.get(str(group_id).strip())
    if override:
        return override.enabled, True
    return False, False


def build_group_policy_item(snap, group: dict) -> RustRconGroupPolicyItem:
    group_id = str(group["group_id"])
    enabled, customized = _group_policy_values(snap, group_id)
    return RustRconGroupPolicyItem(
        group_id=group_id,
        group_name=group.get("group_name"),
        member_count=group.get("member_count"),
        customized=customized,
        enabled=enabled,
    )


def build_group_policy_items(
    snap, groups: list[dict]
) -> list[RustRconGroupPolicyItem]:
    return [build_group_policy_item(snap, group) for group in groups]


def _user_policy_values(snap, user_id: str) -> tuple[bool, bool]:
    override = snap.rust_rcon_user_policies.get(str(user_id).strip())
    if override:
        return override.enabled, True
    return False, False


def build_user_policy_item(snap, user: dict) -> RustRconUserPolicyItem:
    user_id = str(user["user_id"])
    enabled, customized = _user_policy_values(snap, user_id)
    override = snap.rust_rcon_user_policies.get(user_id)
    return RustRconUserPolicyItem(
        user_id=user_id,
        nickname=user.get("nickname"),
        name=override.name if override else None,
        customized=customized,
        enabled=enabled,
    )


def build_user_policy_items(
    snap,
    users: list[dict],
    *,
    include_configured_non_friends: bool = False,
) -> list[RustRconUserPolicyItem]:
    by_id: dict[str, dict] = {str(user["user_id"]): user for user in users}

    if include_configured_non_friends:
        for user_id, record in snap.rust_rcon_user_policies.items():
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


def onebot_list_listing_mode(
    status: Literal["ok", "offline", "incomplete"],
) -> Literal["map", "empty", "partial"]:
    if status == "ok":
        return "map"
    if status == "incomplete":
        return "partial"
    return "empty"
