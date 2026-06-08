"""OneBot group list schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class GroupInfo(BaseModel):
    group_id: str
    group_name: Optional[str] = None
    member_count: Optional[int] = None


class GroupListResponse(BaseModel):
    groups: List[GroupInfo]
