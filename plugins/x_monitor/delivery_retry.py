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


def encode_pending_ids(ids: list[str]) -> str:
    return ",".join(id_ for id_ in ids if id_)


def decode_pending_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part for part in str(raw).split(",") if part]
