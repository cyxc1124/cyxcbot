"""Douyin login API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DouyinQrcodeStartResponse(BaseModel):
    session_id: str
    image_base64: str = Field(description="PNG screenshot of Douyin login QR (base64)")


class DouyinQrcodePollRequest(BaseModel):
    session_id: str = Field(min_length=1)


class DouyinQrcodeLoginResponse(BaseModel):
    success: bool
    message: str
    configured: bool = False
    preview: str | None = None


class DouyinLogoutResponse(BaseModel):
    success: bool
    message: str
