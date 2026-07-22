"""Rust RCON per-group / per-user policy resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot


@dataclass(frozen=True)
class RustRconGroupPolicyRecord:
    group_id: str
    enabled: bool = False


@dataclass(frozen=True)
class RustRconUserPolicyRecord:
    user_id: str
    enabled: bool = False
    name: str | None = None


def is_rust_rcon_enabled(
    snapshot: AppConfigSnapshot,
    *,
    group_id: str | None = None,
    user_id: str | None = None,
    is_private: bool = False,
) -> bool:
    """Return whether Rust RCON commands are allowed in the chat context."""
    if is_private:
        if user_id:
            override = snapshot.rust_rcon_user_policies.get(str(user_id).strip())
            if override:
                return override.enabled
        return False

    if group_id:
        override = snapshot.rust_rcon_group_policies.get(str(group_id).strip())
        if override:
            return override.enabled

    return False
