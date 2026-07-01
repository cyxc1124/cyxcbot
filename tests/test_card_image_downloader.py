"""Tests for live monitor card image downloader cache/session reuse."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CARD_GENERATOR_PATH = ROOT / "plugins" / "live_monitor" / "card_generator.py"


def _load_card_generator_module():
    qualified_name = "plugins.live_monitor.card_generator"
    if qualified_name in sys.modules:
        return sys.modules[qualified_name]
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        CARD_GENERATOR_PATH,
        submodule_search_locations=[str(CARD_GENERATOR_PATH.parent)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


card_generator = _load_card_generator_module()
CardImageDownloader = card_generator.CardImageDownloader
close_card_image_downloader = card_generator.close_card_image_downloader
init_card_image_downloader = card_generator.init_card_image_downloader


def _png_bytes(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    img = Image.new("RGB", (8, 8), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
async def downloader():
    dl = CardImageDownloader(ttl_seconds=60, max_entries=8, max_bytes=1024 * 1024)
    yield dl
    await dl.close()


@pytest.mark.asyncio
async def test_same_url_downloads_once_within_ttl(downloader: CardImageDownloader):
    url = "https://example.com/avatar.png"
    payload = _png_bytes()
    fetch = AsyncMock(return_value=payload)
    downloader._fetch_bytes = fetch  # type: ignore[method-assign]

    first = await downloader.download(url)
    second = await downloader.download(url)

    assert first is not None
    assert second is not None
    assert first.size == second.size
    fetch.assert_awaited_once_with(url)


@pytest.mark.asyncio
async def test_cache_expires_and_refetches(downloader: CardImageDownloader):
    url = "https://example.com/cover.png"
    fetch = AsyncMock(side_effect=[_png_bytes((1, 2, 3)), _png_bytes((4, 5, 6))])
    downloader._fetch_bytes = fetch  # type: ignore[method-assign]

    await downloader.download(url)
    downloader._cache[url] = (downloader._cache[url][0], 0.0)

    await downloader.download(url)

    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_download_failure_returns_none(downloader: CardImageDownloader):
    downloader._fetch_bytes = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await downloader.download("https://example.com/missing.png")

    assert result is None


@pytest.mark.asyncio
async def test_close_clears_session_and_cache(downloader: CardImageDownloader):
    await downloader.ensure_session()
    downloader._set_cached_bytes("https://example.com/a.png", _png_bytes())

    await downloader.close()

    assert downloader._session is None
    assert not downloader._cache


@pytest.mark.asyncio
async def test_concurrent_same_url_only_fetches_once(downloader: CardImageDownloader):
    url = "https://example.com/face.png"
    gate = asyncio.Event()
    payload = _png_bytes()
    fetch_count = 0

    async def slow_fetch(_url: str):
        nonlocal fetch_count
        fetch_count += 1
        await gate.wait()
        return payload

    downloader._fetch_bytes = slow_fetch  # type: ignore[method-assign]

    task1 = asyncio.create_task(downloader.download(url))
    task2 = asyncio.create_task(downloader.download(url))
    await asyncio.sleep(0)
    gate.set()
    img1, img2 = await asyncio.gather(task1, task2)

    assert img1 is not None and img2 is not None
    assert fetch_count == 1


@pytest.mark.asyncio
async def test_module_close_resets_singleton():
    mock_downloader = CardImageDownloader()
    mock_downloader.close = AsyncMock()
    card_generator._card_image_downloader = mock_downloader
    try:
        await close_card_image_downloader()
        mock_downloader.close.assert_awaited_once()
        assert card_generator._card_image_downloader is None
    finally:
        if card_generator._card_image_downloader is not None:
            await card_generator._card_image_downloader.close()
            card_generator._card_image_downloader = None
