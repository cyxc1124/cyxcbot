"""Status check policy API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from admin.schemas.groups import GroupInfo
from admin.schemas.private import FriendInfo


class StatusCheckDisplayOptions(BaseModel):
    show_detailed: bool
    show_uptime: bool
    show_memory: bool


class StatusCheckDisplayUpdateRequest(BaseModel):
    show_detailed: bool
    show_uptime: bool
    show_memory: bool


class GroupStatusPolicyResponse(BaseModel):
    restrict: bool
    enabled_group_ids: List[str]
    groups: List[GroupInfo]
    display: StatusCheckDisplayOptions


class GroupStatusPolicyUpdateRequest(BaseModel):
    restrict: bool
    enabled_group_ids: List[str] = []
    display: Optional[StatusCheckDisplayUpdateRequest] = None


class PrivateStatusPolicyResponse(BaseModel):
    restrict: bool
    enabled_user_ids: List[str]
    users: List[FriendInfo]
    display: StatusCheckDisplayOptions


class PrivateStatusPolicyUpdateRequest(BaseModel):
    restrict: bool
    enabled_user_ids: List[str] = []
    display: Optional[StatusCheckDisplayUpdateRequest] = None
