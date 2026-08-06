"""Schemas for Rust RCON custom command admin API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from shared.config.rust_rcon import normalize_allowed_qq_ids
from shared.config.rust_rcon_custom import (
    normalize_custom_command_name,
    normalize_custom_command_template,
)


class RustRconCustomCommandResponse(BaseModel):
    id: int
    name: str
    template: str
    binding_id: int
    enabled: bool
    allowed_qq_ids: List[str]
    created_at: datetime
    updated_at: datetime


class RustRconCustomCommandListResponse(BaseModel):
    items: List[RustRconCustomCommandResponse]


class RustRconCustomCommandCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    template: str = Field(min_length=1, max_length=512)
    binding_id: int
    allowed_qq_ids: List[str] = Field(min_length=1)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_custom_command_name(value)

    @field_validator("template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        return normalize_custom_command_template(value)

    @field_validator("allowed_qq_ids")
    @classmethod
    def validate_allowed_qq_ids(cls, value: List[str]) -> List[str]:
        return normalize_allowed_qq_ids(value)


class RustRconCustomCommandUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=32)
    template: Optional[str] = Field(default=None, min_length=1, max_length=512)
    binding_id: Optional[int] = None
    allowed_qq_ids: Optional[List[str]] = None
    enabled: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_custom_command_name(value)

    @field_validator("template")
    @classmethod
    def validate_template(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_custom_command_template(value)

    @field_validator("allowed_qq_ids")
    @classmethod
    def validate_allowed_qq_ids(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        return normalize_allowed_qq_ids(value)
