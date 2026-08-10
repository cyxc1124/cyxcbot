"""Helpers for partial X notification delivery retries."""

from __future__ import annotations

from typing import List, Optional, Tuple

from shared.notify.delivery import DeliveryResult

PendingDelivery = Tuple[str, List[str], List[str]]


def failed_target_ids(delivery: DeliveryResult) -> tuple[list[str], list[str]]:
    groups = [
        target.target_id
        for target in delivery.targets
        if target.target_type == "group" and not target.success
    ]
    users = [
        target.target_id
        for target in delivery.targets
        if target.target_type == "user" and not target.success
    ]
    return groups, users


def resolve_retry_targets(
    tweet_id: str,
    *,
    configured_groups: list[str],
    configured_users: list[str],
    pending: Optional[PendingDelivery],
) -> tuple[list[str], list[str], bool]:
    """Resolve group/user ids for a tweet send, honoring pending retries.

    Returns ``(group_ids, user_ids, clear_pending)``.

    When a pending retry's failed recipients were all removed/replaced in
    config, fall back to the current mapping instead of treating the tweet as
    delivered — otherwise a full-failure followed by recipient replacement
    permanently skips the tweet.
    """
    if pending and pending[0] == tweet_id:
        configured_group_set = set(configured_groups)
        configured_user_set = set(configured_users)
        group_ids = [g for g in pending[1] if g in configured_group_set]
        user_ids = [u for u in pending[2] if u in configured_user_set]
        if group_ids or user_ids:
            return group_ids, user_ids, False
        return list(configured_groups), list(configured_users), True

    return list(configured_groups), list(configured_users), bool(pending)


def encode_pending_ids(ids: list[str]) -> str:
    return ",".join(id_ for id_ in ids if id_)


def decode_pending_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part for part in str(raw).split(",") if part]
