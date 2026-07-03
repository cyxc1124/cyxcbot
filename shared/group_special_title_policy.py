"""Group special title command scope policy."""

from __future__ import annotations

DEFAULT_DAILY_USAGE_LIMIT = 10


def is_group_special_title_enabled(
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


def is_group_special_title_enabled_from_snapshot(group_id: str, snapshot) -> bool:
    return is_group_special_title_enabled(
        group_id,
        restrict=snapshot.group_special_title_restrict,
        enabled_group_ids=snapshot.group_special_title_enabled_group_ids,
    )


def daily_usage_limit_from_snapshot(snapshot) -> int:
    return snapshot.group_special_title_daily_limit
