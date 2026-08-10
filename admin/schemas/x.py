"""X (Twitter) admin API schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class XBearerSaveRequest(BaseModel):
    bearer: str = Field(min_length=1, max_length=4096)


class XBearerStatusResponse(BaseModel):
    configured: bool
    preview: Optional[str] = None
    message: str = ""


class XBearerTestRequest(BaseModel):
    username: str = Field(default="X", min_length=1, max_length=64)


class XBearerTestResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None
    name: Optional[str] = None
    user_id: Optional[str] = None
