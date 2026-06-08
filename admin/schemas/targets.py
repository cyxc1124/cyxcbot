"""Target mapping API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DynamicTargetBase(BaseModel):
    uid: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool = True
    group_ids: List[str] = Field(default_factory=list)


class DynamicTargetCreate(DynamicTargetBase):
    pass


class DynamicTargetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: Optional[bool] = None
    group_ids: Optional[List[str]] = None


class DynamicTargetResponse(BaseModel):
    id: int
    uid: str
    name: Optional[str]
    enabled: bool
    group_ids: List[str]
    created_at: datetime
    updated_at: datetime


class LiveTargetBase(BaseModel):
    room_id: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: bool = True
    group_ids: List[str] = Field(default_factory=list)


class LiveTargetCreate(LiveTargetBase):
    pass


class LiveTargetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    enabled: Optional[bool] = None
    group_ids: Optional[List[str]] = None


class LiveTargetResponse(BaseModel):
    id: int
    room_id: str
    name: Optional[str]
    enabled: bool
    group_ids: List[str]
    created_at: datetime
    updated_at: datetime
