"""In-memory pending Steam bind requests (verification code flow)."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

_BIND_PENDING_TTL_SEC = 600.0

# ponytail: process-local; bot restart clears pending binds (user restarts flow)
_pending: dict[str, PendingSteamBind] = {}


@dataclass(frozen=True)
class PendingSteamBind:
    steam_id: str
    verify_code: str
    expires_at: float


def _purge_expired() -> None:
    now = time.monotonic()
    for user_id in [uid for uid, row in _pending.items() if row.expires_at <= now]:
        del _pending[user_id]


def create_pending_bind(user_id: str, steam_id: str) -> str:
    _purge_expired()
    user_id = str(user_id).strip()
    code = secrets.token_hex(3).upper()
    _pending[user_id] = PendingSteamBind(
        steam_id=str(steam_id).strip(),
        verify_code=code,
        expires_at=time.monotonic() + _BIND_PENDING_TTL_SEC,
    )
    return code


def restore_pending_bind(user_id: str, pending: PendingSteamBind) -> None:
    _purge_expired()
    user_id = str(user_id).strip()
    _pending[user_id] = PendingSteamBind(
        steam_id=pending.steam_id,
        verify_code=pending.verify_code,
        expires_at=time.monotonic() + _BIND_PENDING_TTL_SEC,
    )


def consume_pending_bind(user_id: str) -> PendingSteamBind | None:
    _purge_expired()
    user_id = str(user_id).strip()
    pending = _pending.pop(user_id, None)
    if pending is None or pending.expires_at <= time.monotonic():
        return None
    return pending
