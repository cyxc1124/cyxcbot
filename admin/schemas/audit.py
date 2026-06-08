"""Audit and event API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    actor_user_id: Optional[int]
    actor_username: Optional[str]
    ip_address: Optional[str]
    details: Optional[str]
    created_at: datetime


class SystemEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    message: str
    details: Optional[str]
    created_at: datetime
