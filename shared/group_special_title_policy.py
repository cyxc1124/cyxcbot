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


def _message_enabled_group_ids_from_snapshot(snapshot) -> list[str]:
    if snapshot.message_group_restrict:
        return [
            str(gid).strip()
            for gid in snapshot.message_enabled_group_ids
            if str(gid).strip()
        ]
    return []


def special_title_relevant_group_ids(snapshot) -> list[str]:
    """IDs that must appear in a fetched group list for the title policy to be complete."""
    if snapshot.group_special_title_restrict:
        ids = [
            str(gid).strip()
            for gid in snapshot.group_special_title_enabled_group_ids
            if str(gid).strip()
        ]
        if snapshot.message_group_restrict:
            message_enabled = set(_message_enabled_group_ids_from_snapshot(snapshot))
            ids = [gid for gid in ids if gid in message_enabled]
        return ids
    return _message_enabled_group_ids_from_snapshot(snapshot)


def raw_group_ids(raw_groups: list[dict]) -> set[str]:
    return {
        str(group["group_id"])
        for group in raw_groups
        if str(group.get("group_id", "")).strip()
    }


def special_title_policy_group_list_available(
    fetch_available: bool,
    raw_groups: list[dict],
    snapshot,
) -> bool:
    """Return whether the fetched group list is complete for special-title policy edits."""
    if not fetch_available:
        return False
    relevant = special_title_relevant_group_ids(snapshot)
    if not relevant:
        return True
    return all(gid in raw_group_ids(raw_groups) for gid in relevant)


def filter_enabled_group_ids_to_visible_groups(
    enabled_ids: list[str],
    groups: list[dict],
    *,
    group_list_available: bool = True,
) -> list[str]:
    """Drop IDs not in *groups*.

    When *group_list_available* is false (OneBot offline / fetch failed), preserve
    *enabled_ids* unchanged so offline saves do not wipe the whitelist.
    """
    if not group_list_available:
        return enabled_ids
    allowed = {str(group["group_id"]) for group in groups}
    return [gid for gid in enabled_ids if gid in allowed]
