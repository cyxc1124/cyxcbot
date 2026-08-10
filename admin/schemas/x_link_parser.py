"""X link parser policy schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class XLinkParserGroupPolicyItem(BaseModel):
    group_id: str
    group_name: Optional[str] = None
    member_count: Optional[int] = None
    customized: bool
    enabled: bool


class XLinkParserGroupPolicyListResponse(BaseModel):
    groups: List[XLinkParserGroupPolicyItem]
    group_list_available: bool = True


class XLinkParserGroupPolicyMutationResponse(BaseModel):
    item: XLinkParserGroupPolicyItem


class XLinkParserGroupPolicyUpdateRequest(BaseModel):
    enabled: bool


class XLinkParserUserPolicyItem(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    name: Optional[str] = None
    customized: bool
    enabled: bool


class XLinkParserUserPolicyListResponse(BaseModel):
    users: List[XLinkParserUserPolicyItem]
    friend_list_available: bool = True


class XLinkParserUserPolicyMutationResponse(BaseModel):
    item: XLinkParserUserPolicyItem


class XLinkParserUserPolicyCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool = False


class XLinkParserUserPolicyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool
