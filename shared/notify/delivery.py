"""Structured delivery results for monitor notification senders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class TargetDelivery:
    """Per-target send outcome."""

    target_type: str
    target_id: str
    success: bool
    error: Optional[str] = None


@dataclass
class DeliveryResult:
    """Aggregate send outcome for one notification attempt."""

    targets: List[TargetDelivery] = field(default_factory=list)

    @property
    def attempted(self) -> bool:
        return bool(self.targets)

    @property
    def all_succeeded(self) -> bool:
        return self.attempted and all(target.success for target in self.targets)

    @property
    def any_succeeded(self) -> bool:
        return any(target.success for target in self.targets)

    @property
    def all_failed(self) -> bool:
        return self.attempted and not self.any_succeeded

    def merge(self, other: DeliveryResult) -> DeliveryResult:
        return DeliveryResult(targets=[*self.targets, *other.targets])


def empty_delivery_result() -> DeliveryResult:
    return DeliveryResult()
