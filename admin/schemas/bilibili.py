"""Bilibili login API schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class QrcodeStartResponse(BaseModel):
    url: str
    qrcode: dict[str, Any] = Field(
        description="Full Bilibili get_qrcode response for polling"
    )


class QrcodePollRequest(BaseModel):
    qrcode: dict[str, Any]


class QrcodeLoginResponse(BaseModel):
    success: bool
    username: Optional[str] = None
    uid: Optional[str] = None
    message: str


class LogoutResponse(BaseModel):
    success: bool
    message: str
