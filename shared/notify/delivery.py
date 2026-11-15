"""Structured delivery results for monitor notification senders."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import List, Optional

from nonebot.adapters.onebot.v11 import Message, MessageSegment

from shared.notify.pending_media import externalize_segments, inline_segments


class DeliveryCancelledError(RuntimeError):
    """监控投递目标在发送前已失效。"""


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


def aggregate_by_target(result: DeliveryResult) -> DeliveryResult:
    """按配置目标聚合投递结果，任一 bot 成功即视为该目标成功。"""
    grouped: dict[tuple[str, str], list[TargetDelivery]] = {}
    for target in result.targets:
        key = (target.target_type, target.target_id)
        grouped.setdefault(key, []).append(target)

    aggregated: List[TargetDelivery] = []
    for (target_type, target_id), attempts in grouped.items():
        if any(attempt.success for attempt in attempts):
            aggregated.append(TargetDelivery(target_type, target_id, True))
            continue

        errors = [attempt.error for attempt in attempts if attempt.error]
        aggregated.append(
            TargetDelivery(
                target_type,
                target_id,
                False,
                errors[0] if errors else None,
            )
        )
    return DeliveryResult(targets=aggregated)


def empty_delivery_result() -> DeliveryResult:
    return DeliveryResult()


DeliveryProgressCallback = Callable[[str, str, int], Awaitable[None]]

# 目标持续投递失败超过该时长后放弃，否则失效的群/好友会让游标永远停在同一条通知上。
PENDING_DELIVERY_MAX_AGE_SECONDS = 6 * 3600


@dataclass
class PendingDelivery:
    message: Message
    groups: list[str]
    users: list[str]
    at_all: bool = False
    group_starts: dict[str, int] = field(default_factory=dict)
    user_starts: dict[str, int] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def expired(self, now: float | None = None) -> bool:
        return (now or time.time()) - self.created_at > PENDING_DELIVERY_MAX_AGE_SECONDS

    def to_data(self) -> dict:
        return {
            "message": externalize_segments(
                [
                    {"type": segment.type, "data": segment.data}
                    for segment in self.message
                ]
            ),
            "groups": self.groups,
            "users": self.users,
            "at_all": self.at_all,
            "group_starts": self.group_starts,
            "user_starts": self.user_starts,
            "created_at": self.created_at,
        }

    @classmethod
    def from_data(cls, data: dict) -> "PendingDelivery":
        return cls(
            message=Message(
                MessageSegment(**segment)
                for segment in inline_segments(data["message"])
            ),
            groups=data["groups"],
            users=data["users"],
            at_all=data["at_all"],
            group_starts=data["group_starts"],
            user_starts=data["user_starts"],
            # 旧状态没有时间戳：从加载时开始计时。
            created_at=data.get("created_at", time.time()),
        )
