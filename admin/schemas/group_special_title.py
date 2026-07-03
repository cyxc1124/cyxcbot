"""Group special title policy API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from admin.schemas.groups import GroupInfo


class GroupSpecialTitlePolicyResponse(BaseModel):
    restrict: bool
    enabled_group_ids: List[str]
    groups: List[GroupInfo]
    daily_limit: int


class GroupSpecialTitlePolicyUpdateRequest(BaseModel):
    restrict: bool
    enabled_group_ids: List[str] = []
    daily_limit: Optional[int] = Field(None, ge=0, le=100)
