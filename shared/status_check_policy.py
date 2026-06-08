"""Status check (/status) scope policy for groups and friends."""

from __future__ import annotations


def is_status_check_enabled_for_group(
    group_id: str,
    *,
    restrict: bool,
    enabled_group_ids: list[str],
) -> bool:
    if not restrict:
        return True
    gid = str(group_id).strip()
    enabled = {str(item).strip() for item in enabled_group_ids if str(item).strip()}
    return gid in enabled


def is_status_check_enabled_for_user(
    user_id: str,
    *,
    restrict: bool,
    enabled_user_ids: list[str],
) -> bool:
    if not restrict:
        return True
    uid = str(user_id).strip()
    enabled = {str(item).strip() for item in enabled_user_ids if str(item).strip()}
    return uid in enabled


def is_status_check_enabled_for_group_from_snapshot(group_id: str, snapshot) -> bool:
    return is_status_check_enabled_for_group(
        group_id,
        restrict=snapshot.status_check_group_restrict,
        enabled_group_ids=snapshot.status_check_enabled_group_ids,
    )


def is_status_check_enabled_for_user_from_snapshot(user_id: str, snapshot) -> bool:
    return is_status_check_enabled_for_user(
        user_id,
        restrict=snapshot.status_check_private_restrict,
        enabled_user_ids=snapshot.status_check_enabled_user_ids,
    )
