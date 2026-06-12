"""Common API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from admin.auth.password import ensure_password_byte_length

Username = Annotated[str, Field(min_length=3, max_length=64)]
Password = Annotated[
    str,
    Field(min_length=8, max_length=128),
    AfterValidator(ensure_password_byte_length),
]


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
