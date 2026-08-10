"""Per-group / per-user X link parser policy (enabled only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot


@dataclass(frozen=True)
class XLinkParserScopePolicy:
    enabled: bool = False


@dataclass(frozen=True)
class XLinkParserGroupPolicyRecord:
    group_id: str
    enabled: bool = False


@dataclass(frozen=True)
class XLinkParserUserPolicyRecord:
    user_id: str
    enabled: bool = False
    name: str | None = None


def resolve_x_link_parser_policy(
    snapshot: AppConfigSnapshot,
    *,
    group_id: str | None = None,
    user_id: str | None = None,
    is_private: bool = False,
) -> XLinkParserScopePolicy:
    if is_private:
        user_override = snapshot.x_link_parser_user_policies.get(
            str(user_id or "").strip()
        )
        if user_override:
            return XLinkParserScopePolicy(enabled=user_override.enabled)
        return XLinkParserScopePolicy()
    if group_id:
        group_override = snapshot.x_link_parser_group_policies.get(
            str(group_id).strip()
        )
        if group_override:
            return XLinkParserScopePolicy(enabled=group_override.enabled)
    return XLinkParserScopePolicy()
