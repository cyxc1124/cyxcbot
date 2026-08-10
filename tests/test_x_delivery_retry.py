"""Tests for X monitor partial delivery retry helpers."""

from __future__ import annotations

from plugins.x_monitor.delivery_retry import failed_target_ids
from shared.notify.delivery import DeliveryResult, TargetDelivery


def test_failed_target_ids_splits_groups_and_users():
    delivery = DeliveryResult(
        targets=[
            TargetDelivery("group", "1", True),
            TargetDelivery("group", "2", False, "boom"),
            TargetDelivery("user", "9", False, "gone"),
            TargetDelivery("user", "8", True),
        ]
    )
    assert failed_target_ids(delivery) == (["2"], ["9"])
