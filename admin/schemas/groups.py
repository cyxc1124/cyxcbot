"""OneBot group list schemas."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


class GroupInfo(BaseModel):
    group_id: str
    group_name: Optional[str] = None
    member_count: Optional[int] = None
    source: Optional[Literal["onebot", "official"]] = None


class GroupListResponse(BaseModel):
    groups: List[GroupInfo]


class GroupMessagePolicyResponse(BaseModel):
    restrict: bool
    enabled_group_ids: List[str]
    groups: List[GroupInfo]
    group_list_available: bool = True
    onebot_list_status: Optional[Literal["ok", "offline", "incomplete"]] = None


class GroupMessagePolicyUpdateRequest(BaseModel):
    restrict: bool
    enabled_group_ids: List[str] = []
