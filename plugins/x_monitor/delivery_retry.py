"""Helpers for partial X notification delivery retries."""

from __future__ import annotations

from shared.notify.delivery import DeliveryResult


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
