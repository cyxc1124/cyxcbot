"""Rust RCON binding API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RustRconPasswordStatus(BaseModel):
    configured: bool
    preview: Optional[str] = None


class RustRconBindingCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=32)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=28016, ge=1, le=65535)
    password: str = Field(min_length=1)
    enabled: bool = True
    name: Optional[str] = Field(default=None, max_length=128)
    allowed_qq_ids: List[str] = Field(min_length=1)


class RustRconBindingUpdate(BaseModel):
    alias: Optional[str] = Field(default=None, min_length=1, max_length=32)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    password: Optional[str] = None
    enabled: Optional[bool] = None
    name: Optional[str] = Field(default=None, max_length=128)
    allowed_qq_ids: Optional[List[str]] = None


class RustRconBindingResponse(BaseModel):
    id: int
    alias: str
    host: str
    port: int
    password: RustRconPasswordStatus
    enabled: bool
    name: Optional[str]
    allowed_qq_ids: List[str]
    created_at: datetime
    updated_at: datetime
