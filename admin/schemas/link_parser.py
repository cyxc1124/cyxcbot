"""Link parser per-group / per-user policy schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LinkParserGroupPolicyItem(BaseModel):
    group_id: str
    group_name: Optional[str] = None
    member_count: Optional[int] = None
    customized: bool
    video_enabled: bool
    live_enabled: bool


class LinkParserGroupPolicyListResponse(BaseModel):
    groups: List[LinkParserGroupPolicyItem]


class LinkParserGroupPolicyMutationResponse(BaseModel):
    item: LinkParserGroupPolicyItem


class LinkParserGroupPolicyUpdateRequest(BaseModel):
    video_enabled: bool
    live_enabled: bool


class LinkParserUserPolicyItem(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    name: Optional[str] = None
    customized: bool
    video_enabled: bool
    live_enabled: bool


class LinkParserUserPolicyListResponse(BaseModel):
    users: List[LinkParserUserPolicyItem]


class LinkParserUserPolicyMutationResponse(BaseModel):
    item: LinkParserUserPolicyItem


class LinkParserUserPolicyCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    video_enabled: bool = False
    live_enabled: bool = False


class LinkParserUserPolicyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    video_enabled: bool
    live_enabled: bool
