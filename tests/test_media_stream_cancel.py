import asyncio

import pytest

from utils.douyin_api.download import _persist_stream


@pytest.mark.asyncio
async def test_cancelled_stream_removes_partial_without_replacing_existing_file(
    tmp_path,
):
    destination = tmp_path / "video.mp4"
    destination.write_bytes(b"previous")
    started = asyncio.Event()

    async def chunks():
        yield b"partial"
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(
        _persist_stream(chunks(), destination, None, max_bytes=32)
    )
    await started.wait()
    partial = destination.with_suffix(".mp4.tmp")
    assert partial.exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not partial.exists()
    assert destination.read_bytes() == b"previous"
