"""Runtime log API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LogEntryResponse(BaseModel):
    ts: str
    level: str
    logger: str
    message: str


class RecentLogsResponse(BaseModel):
    items: list[LogEntryResponse]
    total_buffered: int = Field(description="Current in-memory buffer size")
