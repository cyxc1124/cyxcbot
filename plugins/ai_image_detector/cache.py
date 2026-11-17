"""Reuse detection replies for identical image bytes; Web Admin reviews them."""

from __future__ import annotations

import asyncio

from nonebot_plugin_orm import get_session
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, select, update

from shared.db.defaults import utcnow
from shared.db.models import AiImageCache
from utils.vision_api import preview_jpeg

PREVIEW_EDGE = 512
PREVIEW_QUALITY = 80


async def cached_result(digest: str, fingerprint: str) -> tuple[str, bool] | None:
    """Return (stored reply, edited by admin) and count the hit; None means re-run."""
    async with get_session() as session:
        async with session.begin():
            row = await session.scalar(
                select(AiImageCache).where(AiImageCache.sha256 == digest)
            )
            if row is None or (
                row.edited_at is None and row.config_fingerprint != fingerprint
            ):
                return None
            await session.execute(
                update(AiImageCache)
                .where(AiImageCache.id == row.id)
                .values(hit_count=AiImageCache.hit_count + 1, used_at=utcnow())
            )
            return row.result, row.edited_at is not None


def _preview(data: bytes) -> bytes | None:
    try:
        return preview_jpeg(data, PREVIEW_EDGE, PREVIEW_QUALITY)
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        return None


async def _prune(session, max_entries: int) -> None:
    # 超出上限时删除最久没有被询问的未修改结果；管理员修改过的结果不计入、不删除。
    overflow = (
        select(AiImageCache.id)
        .where(AiImageCache.edited_at.is_(None))
        .order_by(AiImageCache.used_at.desc(), AiImageCache.id.desc())
        .offset(max_entries)
    )
    await session.execute(
        delete(AiImageCache)
        .where(AiImageCache.id.in_(overflow))
        .execution_options(synchronize_session=False)
    )


async def prune(max_entries: int) -> None:
    """Apply a lowered limit now instead of at the next stored result."""
    async with get_session() as session:
        async with session.begin():
            await _prune(session, max_entries)


async def store_result(
    digest: str,
    data: bytes,
    media_type: str,
    result: str,
    fingerprint: str,
    max_entries: int,
) -> None:
    """Save a complete detection reply unless an admin has edited this image's result."""
    now = utcnow()
    values = {
        "media_type": media_type,
        "size_bytes": len(data),
        "preview": await asyncio.to_thread(_preview, data),
        "result": result,
        "config_fingerprint": fingerprint,
        "hit_count": 0,
        "created_at": now,
        "used_at": now,
    }
    async with get_session() as session:
        async with session.begin():
            # 带条件更新：检测期间管理员改过的结果不会被覆盖。
            updated = await session.execute(
                update(AiImageCache)
                .where(AiImageCache.sha256 == digest, AiImageCache.edited_at.is_(None))
                .values(**values)
            )
            if not updated.rowcount and (
                await session.scalar(
                    select(AiImageCache.id).where(AiImageCache.sha256 == digest)
                )
                is None
            ):
                session.add(AiImageCache(sha256=digest, **values))
                await session.flush()
            await _prune(session, max_entries)
