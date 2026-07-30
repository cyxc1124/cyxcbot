"""Short-lived cache for per-user Rust check-in RCON online checks."""

from __future__ import annotations

import time
from dataclasses import dataclass

_CHECKIN_RCON_COOLDOWN_SEC = 60.0

# ponytail: process-local TTL cache; limits repeated status spam per user
_cache: dict[str, _OnlineCheckCache] = {}


@dataclass(frozen=True)
class _OnlineCheckCache:
    checked_at: float
    is_online: bool


def should_cache_checkin_online_result(*, already_checked_in: bool) -> bool:
    """Whether an RCON online probe may reuse/store the per-user TTL cache."""
    # Bonus retries must re-query: offline results are cached during first check-in.
    return not already_checked_in


def get_cached_checkin_online(user_id: str) -> bool | None:
    entry = _cache.get(str(user_id).strip())
    if entry is None:
        return None
    if time.monotonic() - entry.checked_at > _CHECKIN_RCON_COOLDOWN_SEC:
        _cache.pop(str(user_id).strip(), None)
        return None
    return entry.is_online


def set_cached_checkin_online(user_id: str, is_online: bool) -> None:
    _cache[str(user_id).strip()] = _OnlineCheckCache(time.monotonic(), is_online)
