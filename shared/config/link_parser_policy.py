"""Link parser policy resolution: per-group / per-user video & live modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot


@dataclass(frozen=True)
class LinkParserScopePolicy:
    video_enabled: bool = False
    live_enabled: bool = False


@dataclass(frozen=True)
class LinkParserGroupPolicyRecord:
    group_id: str
    video_enabled: bool = False
    live_enabled: bool = False


@dataclass(frozen=True)
class LinkParserUserPolicyRecord:
    user_id: str
    video_enabled: bool = False
    live_enabled: bool = False
    name: str | None = None


def resolve_link_parser_policy(
    snapshot: AppConfigSnapshot,
    *,
    group_id: str | None = None,
    user_id: str | None = None,
    is_private: bool = False,
) -> LinkParserScopePolicy:
    """Resolve effective link parser policy for a chat context."""
    if is_private:
        if user_id:
            user_override = snapshot.link_parser_user_policies.get(str(user_id).strip())
            if user_override:
                return LinkParserScopePolicy(
                    video_enabled=user_override.video_enabled,
                    live_enabled=user_override.live_enabled,
                )
        return LinkParserScopePolicy()

    if group_id:
        group_override = snapshot.link_parser_group_policies.get(str(group_id).strip())
        if group_override:
            return LinkParserScopePolicy(
                video_enabled=group_override.video_enabled,
                live_enabled=group_override.live_enabled,
            )

    return LinkParserScopePolicy()
