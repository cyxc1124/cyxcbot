"""Rust RCON per-group / per-user policy schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RustRconGroupPolicyItem(BaseModel):
    group_id: str
    group_name: Optional[str] = None
    member_count: Optional[int] = None
    customized: bool
    enabled: bool


class RustRconGroupPolicyListResponse(BaseModel):
    groups: List[RustRconGroupPolicyItem]
    group_list_available: bool = True


class RustRconGroupPolicyMutationResponse(BaseModel):
    item: RustRconGroupPolicyItem


class RustRconGroupPolicyUpdateRequest(BaseModel):
    enabled: bool


class RustRconUserPolicyItem(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    name: Optional[str] = None
    customized: bool
    enabled: bool


class RustRconUserPolicyListResponse(BaseModel):
    users: List[RustRconUserPolicyItem]
    friend_list_available: bool = True


class RustRconUserPolicyMutationResponse(BaseModel):
    item: RustRconUserPolicyItem


class RustRconUserPolicyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool
