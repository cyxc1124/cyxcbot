"""Global QQ private message allowlist policy."""

from __future__ import annotations


def is_private_message_enabled(
    user_id: str,
    *,
    restrict: bool,
    enabled_user_ids: list[str],
) -> bool:
    """Return whether the bot should process private messages from this user."""
    if not restrict:
        return True
    uid = str(user_id).strip()
    enabled = {str(item).strip() for item in enabled_user_ids if str(item).strip()}
    return uid in enabled


def is_private_message_enabled_from_snapshot(user_id: str, snapshot) -> bool:
    """Check private message policy using an AppConfigSnapshot."""
    return is_private_message_enabled(
        user_id,
        restrict=snapshot.message_private_restrict,
        enabled_user_ids=snapshot.message_enabled_user_ids,
    )


def filter_enabled_user_ids_to_visible_users(
    enabled_ids: list[str],
    users: list[dict],
    *,
    friend_list_available: bool = True,
) -> list[str]:
    """Drop IDs not in *users*.

    When *friend_list_available* is false, preserve *enabled_ids* unchanged so
    display-only saves do not look like a whitelist shrink.
    """
    if not friend_list_available:
        return list(enabled_ids)
    allowed = {str(user["user_id"]) for user in users}
    return [uid for uid in enabled_ids if uid in allowed]
