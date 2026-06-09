"""Common API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

Username = Annotated[str, Field(min_length=3, max_length=64)]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    message: str


class SetupStatusResponse(BaseModel):
    initialized: bool
    user_count: int


class SetupRequest(BaseModel):
    username: Username
    password: Password


class LoginRequest(BaseModel):
    username: Username
    password: Password


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime
