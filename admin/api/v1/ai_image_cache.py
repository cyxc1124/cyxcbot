"""AI image detection cache: browse answered images, correct or delete results."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from nonebot_plugin_orm import get_session
from sqlalchemy import delete, func, select
from sqlalchemy.orm import defer

from admin.deps import AdminUser, RequireSetup
from admin.schemas.ai_image_cache import (
    AiImageCacheClearResponse,
    AiImageCacheEntry,
    AiImageCacheListResponse,
    AiImageCacheUpdate,
)
from shared.config.ai_image import detection_fingerprint
from shared.config.service import get_config_service
from shared.db.defaults import utcnow
from shared.db.models import AiImageCache

router = APIRouter(
    prefix="/ai-image/cache",
    tags=["ai-image-cache"],
    dependencies=[RequireSetup],
)

MAX_RESULT_LENGTH = 4000
EntryId = Path(ge=1)
_MISSING = "缓存记录不存在或已被删除，请刷新页面后重试"


def _entry(row: AiImageCache, has_preview: bool, fingerprint: str) -> AiImageCacheEntry:
    return AiImageCacheEntry(
        id=row.id,
        sha256=row.sha256,
        media_type=row.media_type,
        size_bytes=row.size_bytes,
        has_preview=has_preview,
        result=row.result,
        edited=row.edited_at is not None,
        stale=row.edited_at is None and row.config_fingerprint != fingerprint,
        hit_count=row.hit_count,
        created_at=row.created_at,
        used_at=row.used_at,
        edited_at=row.edited_at,
    )


def _fingerprint() -> str:
    return detection_fingerprint(get_config_service().get_snapshot())


@router.get("", response_model=AiImageCacheListResponse)
async def list_cache(
    _: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    fingerprint = _fingerprint()
    async with get_session() as session:
        total = await session.scalar(select(func.count()).select_from(AiImageCache))
        rows = (
            await session.execute(
                select(AiImageCache, AiImageCache.preview.is_not(None))
                .options(defer(AiImageCache.preview))
                .order_by(AiImageCache.used_at.desc(), AiImageCache.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items = [_entry(row, has_preview, fingerprint) for row, has_preview in rows]
    return AiImageCacheListResponse(
        items=items, total=total or 0, page=page, page_size=page_size
    )


@router.get("/{entry_id}/preview")
async def get_cache_preview(_: AdminUser, entry_id: int = EntryId):
    async with get_session() as session:
        preview = await session.scalar(
            select(AiImageCache.preview).where(AiImageCache.id == entry_id)
        )
    if preview is None:
        raise HTTPException(status_code=404, detail="这条记录没有可显示的图片")
    # 删除后 id 可能被复用，且图片来自群聊，不让浏览器缓存。
    return Response(
        preview, media_type="image/jpeg", headers={"Cache-Control": "no-store"}
    )


@router.patch("/{entry_id}", response_model=AiImageCacheEntry)
async def update_cache_entry(
    body: AiImageCacheUpdate, _: AdminUser, entry_id: int = EntryId
):
    result = body.result.replace("\r\n", "\n").strip()
    if not result:
        raise HTTPException(status_code=400, detail="回复内容不能为空")
    if len(result) > MAX_RESULT_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"回复内容不能超过 {MAX_RESULT_LENGTH} 个字符"
        )
    fingerprint = _fingerprint()
    async with get_session() as session:
        async with session.begin():
            row = await session.get(AiImageCache, entry_id)
            if row is None:
                raise HTTPException(status_code=404, detail=_MISSING)
            row.result = result
            row.edited_at = utcnow()
            await session.flush()
            return _entry(row, row.preview is not None, fingerprint)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cache_entry(_: AdminUser, entry_id: int = EntryId) -> None:
    async with get_session() as session:
        async with session.begin():
            deleted = await session.execute(
                delete(AiImageCache).where(AiImageCache.id == entry_id)
            )
            if not deleted.rowcount:
                raise HTTPException(status_code=404, detail=_MISSING)


@router.delete("", response_model=AiImageCacheClearResponse)
async def clear_cache(_: AdminUser):
    async with get_session() as session:
        async with session.begin():
            deleted = await session.execute(delete(AiImageCache))
            return AiImageCacheClearResponse(deleted=deleted.rowcount or 0)
