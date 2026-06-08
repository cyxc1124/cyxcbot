"""Link parser per-group / per-user policy schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LinkParserGlobalPolicy(BaseModel):
    enabled: bool
    video_enabled: bool
    live_enabled: bool
    private_enabled: bool


class LinkParserGroupPolicyItem(BaseModel):
    group_id: str
    group_name: Optional[str] = None
    member_count: Optional[int] = None
    customized: bool
    enabled: bool
    video_enabled: bool
    live_enabled: bool


class LinkParserGroupPolicyListResponse(BaseModel):
    global_policy: LinkParserGlobalPolicy
    groups: List[LinkParserGroupPolicyItem]


class LinkParserGroupPolicyUpdateRequest(BaseModel):
    enabled: bool
    video_enabled: bool
    live_enabled: bool


class LinkParserUserPolicyItem(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    name: Optional[str] = None
    customized: bool
    enabled: bool
    video_enabled: bool
    live_enabled: bool
    private_enabled: bool


class LinkParserUserPolicyListResponse(BaseModel):
    global_policy: LinkParserGlobalPolicy
    users: List[LinkParserUserPolicyItem]


class LinkParserUserPolicyCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool = True
    video_enabled: bool = True
    live_enabled: bool = True
    private_enabled: bool = True


class LinkParserUserPolicyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool
    video_enabled: bool
    live_enabled: bool
    private_enabled: bool
