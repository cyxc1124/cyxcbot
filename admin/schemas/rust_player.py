"""Schemas for Rust player admin API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RustPlayerOverviewItem(BaseModel):
    group_id: Optional[str] = None
    user_id: str
    points: int
    steam_id: Optional[str] = None


class RustPlayerOverviewResponse(BaseModel):
    items: List[RustPlayerOverviewItem]


class RustPlayerPointsUpdateRequest(BaseModel):
    group_id: str = Field(min_length=1, max_length=32)
    user_id: str = Field(min_length=1, max_length=32)
    points: int = Field(ge=0, le=1_000_000)


class RustPlayerPointsUpdateResponse(BaseModel):
    group_id: str
    user_id: str
    points: int


class RustCheckInConfigResponse(BaseModel):
    min_points: int
    max_points: int


class RustCheckInConfigUpdateRequest(BaseModel):
    min_points: int = Field(ge=0, le=1_000_000)
    max_points: int = Field(ge=0, le=1_000_000)
