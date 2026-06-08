"""Link parser policy resolution: global defaults with per-group / per-user overrides."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot


@dataclass(frozen=True)
class LinkParserScopePolicy:
    enabled: bool = True
    video_enabled: bool = True
    live_enabled: bool = True
    private_enabled: bool = True


@dataclass(frozen=True)
class LinkParserGroupPolicyRecord:
    group_id: str
    enabled: bool = True
    video_enabled: bool = True
    live_enabled: bool = True


@dataclass(frozen=True)
class LinkParserUserPolicyRecord:
    user_id: str
    enabled: bool = True
    video_enabled: bool = True
    live_enabled: bool = True
    private_enabled: bool = True
    name: str | None = None


def _disabled_policy() -> LinkParserScopePolicy:
    return LinkParserScopePolicy(
        enabled=False,
        video_enabled=False,
        live_enabled=False,
        private_enabled=False,
    )


def _global_policy(snapshot: AppConfigSnapshot) -> LinkParserScopePolicy:
    return LinkParserScopePolicy(
        enabled=snapshot.bilibili_link_parser_enabled,
        video_enabled=snapshot.bilibili_link_parser_video_enabled,
        live_enabled=snapshot.bilibili_link_parser_live_enabled,
        private_enabled=snapshot.bilibili_link_parser_private_enabled,
    )


def resolve_link_parser_policy(
    snapshot: AppConfigSnapshot,
    *,
    group_id: str | None = None,
    user_id: str | None = None,
    is_private: bool = False,
) -> LinkParserScopePolicy:
    """Resolve effective link parser policy for a chat context."""
    policy = _global_policy(snapshot)

    if group_id:
        group_override = snapshot.link_parser_group_policies.get(str(group_id).strip())
        if group_override:
            policy = LinkParserScopePolicy(
                enabled=group_override.enabled,
                video_enabled=group_override.video_enabled,
                live_enabled=group_override.live_enabled,
                private_enabled=policy.private_enabled,
            )

    if user_id:
        user_override = snapshot.link_parser_user_policies.get(str(user_id).strip())
        if user_override:
            policy = LinkParserScopePolicy(
                enabled=user_override.enabled,
                video_enabled=user_override.video_enabled,
                live_enabled=user_override.live_enabled,
                private_enabled=(
                    user_override.private_enabled if is_private else policy.private_enabled
                ),
            )

    if not policy.enabled:
        return _disabled_policy()
    if is_private and not policy.private_enabled:
        return _disabled_policy()

    return policy
