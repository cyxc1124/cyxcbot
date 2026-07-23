"""Schemas for Rust player admin API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from shared.config.rust_player import normalize_player_points


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
    points: int

    @field_validator("points")
    @classmethod
    def validate_points(cls, value: int) -> int:
        return normalize_player_points(value)


class RustPlayerPointsUpdateResponse(BaseModel):
    group_id: str
    user_id: str
    points: int


class RustCheckInConfigResponse(BaseModel):
    min_points: int
    max_points: int
    online_bonus_points: int
    rcon_binding_id: int


class RustCheckInConfigUpdateRequest(BaseModel):
    min_points: int
    max_points: int
    online_bonus_points: int
    rcon_binding_id: int

    @field_validator("min_points", "max_points", "online_bonus_points")
    @classmethod
    def validate_points(cls, value: int) -> int:
        return normalize_player_points(value)

    @field_validator("rcon_binding_id")
    @classmethod
    def validate_rcon_binding_id(cls, value: int) -> int:
        from shared.config.rust_player import normalize_checkin_rcon_binding_id

        return normalize_checkin_rcon_binding_id(value)
