"""Link parser policy resolution: per-group / per-user video, live & dynamic modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot


@dataclass(frozen=True)
class LinkParserScopePolicy:
    video_enabled: bool = False
    live_enabled: bool = False
    dynamic_enabled: bool = False
    send_video_enabled: bool = False


@dataclass(frozen=True)
class LinkParserGroupPolicyRecord:
    group_id: str
    video_enabled: bool = False
    live_enabled: bool = False
    dynamic_enabled: bool = False
    send_video_enabled: bool = False


@dataclass(frozen=True)
class LinkParserUserPolicyRecord:
    user_id: str
    video_enabled: bool = False
    live_enabled: bool = False
    dynamic_enabled: bool = False
    send_video_enabled: bool = False
    name: str | None = None


def normalize_link_parser_flags(
    *,
    video_enabled: bool,
    live_enabled: bool,
    dynamic_enabled: bool,
    send_video_enabled: bool,
) -> tuple[bool, bool, bool, bool]:
    """发送视频依赖视频链接解析；video 关闭时强制关掉 send_video。"""
    video = bool(video_enabled)
    return (
        video,
        bool(live_enabled),
        bool(dynamic_enabled),
        bool(send_video_enabled) and video,
    )


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
                video, live, dynamic, send = normalize_link_parser_flags(
                    video_enabled=user_override.video_enabled,
                    live_enabled=user_override.live_enabled,
                    dynamic_enabled=user_override.dynamic_enabled,
                    send_video_enabled=user_override.send_video_enabled,
                )
                return LinkParserScopePolicy(
                    video_enabled=video,
                    live_enabled=live,
                    dynamic_enabled=dynamic,
                    send_video_enabled=send,
                )
        return LinkParserScopePolicy()

    if group_id:
        group_override = snapshot.link_parser_group_policies.get(str(group_id).strip())
        if group_override:
            video, live, dynamic, send = normalize_link_parser_flags(
                video_enabled=group_override.video_enabled,
                live_enabled=group_override.live_enabled,
                dynamic_enabled=group_override.dynamic_enabled,
                send_video_enabled=group_override.send_video_enabled,
            )
            return LinkParserScopePolicy(
                video_enabled=video,
                live_enabled=live,
                dynamic_enabled=dynamic,
                send_video_enabled=send,
            )

    return LinkParserScopePolicy()
