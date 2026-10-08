"""OneBot friend list and private message policy schemas."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


class FriendInfo(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    source: Optional[Literal["onebot", "official"]] = None


class FriendListResponse(BaseModel):
    friends: List[FriendInfo]


class PrivateMessagePolicyResponse(BaseModel):
    restrict: bool
    enabled_user_ids: List[str]
    users: List[FriendInfo]
    friend_list_available: bool = True


class PrivateMessagePolicyUpdateRequest(BaseModel):
    restrict: bool
    enabled_user_ids: List[str] = []
