"""Douyin link parser policy schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DouyinLinkParserGroupPolicyItem(BaseModel):
    group_id: str
    group_name: Optional[str] = None
    member_count: Optional[int] = None
    customized: bool
    enabled: bool


class DouyinLinkParserGroupPolicyListResponse(BaseModel):
    groups: List[DouyinLinkParserGroupPolicyItem]
    group_list_available: bool = True


class DouyinLinkParserGroupPolicyMutationResponse(BaseModel):
    item: DouyinLinkParserGroupPolicyItem


class DouyinLinkParserGroupPolicyUpdateRequest(BaseModel):
    enabled: bool


class DouyinLinkParserUserPolicyItem(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    name: Optional[str] = None
    customized: bool
    enabled: bool


class DouyinLinkParserUserPolicyListResponse(BaseModel):
    users: List[DouyinLinkParserUserPolicyItem]
    friend_list_available: bool = True


class DouyinLinkParserUserPolicyMutationResponse(BaseModel):
    item: DouyinLinkParserUserPolicyItem


class DouyinLinkParserUserPolicyCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool = False


class DouyinLinkParserUserPolicyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool


class DouyinCookieSaveRequest(BaseModel):
    cookie: str = Field(min_length=1)


class DouyinCookieStatusResponse(BaseModel):
    configured: bool
    preview: Optional[str] = None
    message: str = ""


class DouyinCookieClearResponse(BaseModel):
    success: bool = True
    message: str = "已清除抖音 Cookie"
