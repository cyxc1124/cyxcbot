"""Dynamic subscription helpers (independent of push enabled state)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot


def is_group_dynamic_subscribed(group_id: str, snapshot: AppConfigSnapshot) -> bool:
    """Return whether any dynamic target maps this group (push may be disabled)."""
    gid = str(group_id).strip()
    if not gid:
        return False
    for group_ids in snapshot.dynamic_subscription_mapping.values():
        if gid in {str(item).strip() for item in group_ids if str(item).strip()}:
            return True
    return False


def is_user_dynamic_subscribed(user_id: str, snapshot: AppConfigSnapshot) -> bool:
    """Return whether any dynamic target maps this friend (push may be disabled)."""
    uid = str(user_id).strip()
    if not uid:
        return False
    for user_ids in snapshot.dynamic_subscription_user_mapping.values():
        if uid in {str(item).strip() for item in user_ids if str(item).strip()}:
            return True
    return False
