"""Connection status schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class BilibiliConnectionStatus(BaseModel):
    configured: bool
    logged_in: bool
    username: Optional[str] = None
    uid: Optional[str] = None
    message: str


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
