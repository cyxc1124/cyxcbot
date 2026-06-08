"""Global QQ group message allowlist policy."""

from __future__ import annotations


def is_group_message_enabled(
    group_id: str,
    *,
    restrict: bool,
    enabled_group_ids: list[str],
) -> bool:
    """Return whether the bot should process messages from this group."""
    if not restrict:
        return True
    gid = str(group_id).strip()
    enabled = {str(item).strip() for item in enabled_group_ids if str(item).strip()}
    return gid in enabled


def is_group_message_enabled_from_snapshot(group_id: str, snapshot) -> bool:
    """Check group policy using an AppConfigSnapshot."""
    return is_group_message_enabled(
        group_id,
        restrict=snapshot.message_group_restrict,
        enabled_group_ids=snapshot.message_enabled_group_ids,
    )
