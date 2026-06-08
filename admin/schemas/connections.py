"""Connection status schemas."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel

BilibiliConnectionStatusKind = Literal[
    "logged_in",
    "not_configured",
    "session_expired",
    "verify_failed",
]


class BilibiliConnectionStatus(BaseModel):
    status: BilibiliConnectionStatusKind
    configured: bool
    logged_in: bool
    username: Optional[str] = None
    uid: Optional[str] = None


class QqBotInfo(BaseModel):
    qq: str
    nickname: Optional[str] = None


class QqConnectionStatus(BaseModel):
    connected: bool
    bot_count: int
    bots: List[QqBotInfo]
    message: str


class ConnectionsStatusResponse(BaseModel):
    bilibili: BilibiliConnectionStatus
    qq: QqConnectionStatus
