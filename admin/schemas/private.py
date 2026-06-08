"""OneBot friend list and private message policy schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class FriendInfo(BaseModel):
    user_id: str
    nickname: Optional[str] = None


class PrivateMessagePolicyResponse(BaseModel):
    restrict: bool
    enabled_user_ids: List[str]
    users: List[FriendInfo]


class PrivateMessagePolicyUpdateRequest(BaseModel):
    restrict: bool
    enabled_user_ids: List[str] = []
