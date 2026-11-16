"""AI image detection cache schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AiImageCacheEntry(BaseModel):
    id: int
    sha256: str
    media_type: str
    size_bytes: int
    has_preview: bool
    result: str
    edited: bool
    # 未修改且检测配置已变化：下次询问会重新检测。
    stale: bool
    hit_count: int
    created_at: datetime
    used_at: datetime
    edited_at: Optional[datetime] = None


class AiImageCacheListResponse(BaseModel):
    items: list[AiImageCacheEntry] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class AiImageCacheUpdate(BaseModel):
    result: str = Field(max_length=20000)


class AiImageCacheClearResponse(BaseModel):
    deleted: int
