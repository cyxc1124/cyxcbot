"""Cancelled X downloads must leave neither partial nor completed media."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.x_api.download import download_url, materialize_tweet_media
from utils.x_api.models import TweetItem, TweetMediaItem


def _response(chunks):
    response = SimpleNamespace(
        status=200, content=SimpleNamespace(iter_chunked=lambda _: chunks())
    )
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


@pytest.mark.parametrize("completed_count", [0, 1])
async def test_cancelled_download_removes_partial_and_completed_media(
    completed_count, tmp_path
):
    started = asyncio.Event()

    async def complete():
        yield b"completed"

    async def partial():
        yield b"partial"
        started.set()
        await asyncio.Event().wait()

    session = SimpleNamespace(
        get=MagicMock(
            side_effect=[
                *[_response(complete) for _ in range(completed_count)],
                _response(partial),
            ]
        )
    )
    tweet = TweetItem(
        id="200",
        text="",
        created_at="",
        username="author",
        name="Author",
        url="",
        media_items=[
            TweetMediaItem("image", f"https://media.example/{i}.jpg")
            for i in range(completed_count + 1)
        ],
    )
    task = asyncio.create_task(materialize_tweet_media(session, tweet, tmp_path))
    await asyncio.wait_for(started.wait(), 2)
    assert len(list(tmp_path.iterdir())) == completed_count + 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert list(tmp_path.iterdir()) == []
    assert all(item.file_path is None for item in tweet.media_items)


async def test_download_error_and_success_preserve_existing_behavior(tmp_path):
    async def complete():
        yield b"media"

    async def failed():
        yield b"partial"
        raise RuntimeError("download failed")

    for chunks, expected in [(complete, True), (failed, False)]:
        target = tmp_path / f"{expected}.jpg"
        session = SimpleNamespace(get=MagicMock(return_value=_response(chunks)))
        assert (
            await download_url(session, "https://media.example/image", target)
            is expected
        )
        assert target.exists() is expected
        assert not target.with_suffix(".jpg.tmp").exists()
