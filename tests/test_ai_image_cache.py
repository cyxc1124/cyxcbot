"""Detection cache: identical images reuse replies; admins review, edit and delete them."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import ai_image_helpers  # noqa: F401
import pytest
from fastapi import HTTPException
from PIL import Image
from test_config_service_load_perf import db_context as db_context

import plugins.ai_image_detector.cache as cache
from admin.api.v1 import ai_image_cache as cache_api
from admin.schemas.ai_image_cache import AiImageCacheUpdate
from shared.config.ai_image import detection_fingerprint
from shared.config.types import AppConfigSnapshot

CURRENT = detection_fingerprint(AppConfigSnapshot())


def _png(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (900, 600), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def stored(db_context, monkeypatch):
    _, factory, *_ = db_context
    monkeypatch.setattr(cache, "get_session", factory)
    monkeypatch.setattr(cache_api, "get_session", factory)
    snapshot = AppConfigSnapshot()
    monkeypatch.setattr(
        cache_api,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: snapshot),
    )

    async def save(digest: str, result: str, fingerprint: str = CURRENT, data=None):
        await cache.store_result(
            digest, _png() if data is None else data, "image/png", result, fingerprint
        )

    return save


async def _entries():
    return (await cache_api.list_cache(None, page=1, page_size=20)).items


@pytest.mark.asyncio
async def test_results_are_reused_until_the_detection_setup_changes(stored):
    digest = "a" * 64
    await stored(digest, "结论：甲")
    assert await cache.cached_result(digest, CURRENT) == ("结论：甲", False)
    assert await cache.cached_result(digest, "other-setup") is None
    await stored(digest, "结论：乙", "other-setup")
    (entry,) = await _entries()
    assert (entry.result, entry.hit_count, entry.stale) == ("结论：乙", 0, True)
    assert (entry.has_preview, entry.size_bytes) == (True, len(_png()))
    assert await cache.cached_result(digest, "other-setup") == ("结论：乙", False)
    assert (await _entries())[0].hit_count == 1


@pytest.mark.asyncio
async def test_admin_edits_win_and_are_never_pruned(stored, monkeypatch):
    monkeypatch.setattr(cache, "MAX_UNEDITED_ENTRIES", 2)
    for index in range(3):
        await stored(f"{index:064x}", f"结论：{index}")
    entries = await _entries()
    assert [entry.result for entry in entries] == ["结论：2", "结论：1"]

    target = entries[1]
    edited = await cache_api.update_cache_entry(
        AiImageCacheUpdate(result="  结论：管理员复核\r\n已确认\n"), None, target.id
    )
    assert (edited.result, edited.edited, edited.stale) == (
        "结论：管理员复核\n已确认",
        True,
        False,
    )
    # 重新检测与配置变化都不覆盖管理员的修改。
    await stored(target.sha256, "结论：新检测", "other-setup")
    assert await cache.cached_result(target.sha256, "other-setup") == (
        "结论：管理员复核\n已确认",
        True,
    )
    for index in range(3, 6):
        await stored(f"{index:064x}", f"结论：{index}")
    assert sorted(entry.result for entry in await _entries()) == [
        "结论：4",
        "结论：5",
        "结论：管理员复核\n已确认",
    ]


@pytest.mark.asyncio
async def test_deleted_ids_are_never_given_to_another_image(stored):
    await stored("d" * 64, "结论：旧图")
    (old,) = await _entries()
    await cache_api.delete_cache_entry(None, old.id)
    await stored("f" * 64, "结论：新图")
    (new,) = await _entries()
    assert new.id != old.id
    with pytest.raises(HTTPException) as error:
        await cache_api.update_cache_entry(
            AiImageCacheUpdate(result="结论：改错"), None, old.id
        )
    assert error.value.status_code == 404
    assert (await _entries())[0].result == "结论：新图"


@pytest.mark.asyncio
async def test_admin_can_view_previews_and_delete_entries(stored):
    await stored("b" * 64, "结论：有图", data=_png("blue"))
    await stored("c" * 64, "结论：无图", data=b"not an image")
    page = await cache_api.list_cache(None, page=2, page_size=1)
    assert (page.total, len(page.items), page.items[0].result) == (2, 1, "结论：有图")

    with_preview, without_preview = sorted(
        await _entries(), key=lambda entry: not entry.has_preview
    )
    response = await cache_api.get_cache_preview(None, with_preview.id)
    assert response.headers["cache-control"] == "no-store"
    with Image.open(BytesIO(response.body)) as preview:
        assert (preview.format, max(preview.size)) == ("JPEG", 512)
    update = cache_api.update_cache_entry
    for call, status_code in (
        (cache_api.get_cache_preview(None, without_preview.id), 404),
        (update(AiImageCacheUpdate(result="  "), None, without_preview.id), 400),
        (update(AiImageCacheUpdate(result="长" * 4001), None, without_preview.id), 400),
        (update(AiImageCacheUpdate(result="结论"), None, 999), 404),
    ):
        with pytest.raises(HTTPException) as error:
            await call
        assert error.value.status_code == status_code

    await cache_api.delete_cache_entry(None, with_preview.id)
    with pytest.raises(HTTPException) as error:
        await cache_api.delete_cache_entry(None, with_preview.id)
    assert error.value.status_code == 404
    assert (await cache_api.clear_cache(None)).deleted == 1
    assert await _entries() == []
