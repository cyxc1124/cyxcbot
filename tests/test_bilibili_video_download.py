"""Tests for Bilibili DASH stream selection (no network)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.bilibili_api.video_download import (
    DEFAULT_MAX_BYTES,
    BilibiliVideoDownloadError,
    _is_too_large_error,
    _merge_av,
    _reject_if_too_large,
    download_bilibili_video,
    pick_request_qn,
    select_dash_streams,
)


def test_max_bytes_matches_llbot_raw_file_ceiling() -> None:
    """file:// 直读，上限对齐 LuckyLilliaBot SendElement.video 原始文件硬顶。"""
    assert DEFAULT_MAX_BYTES == 1024 * 1024 * 1024


def test_reject_if_too_large_raises_and_deletes(tmp_path: Path) -> None:
    path = tmp_path / "big.mp4"
    path.write_bytes(b"x" * 16)
    with pytest.raises(BilibiliVideoDownloadError, match="超过发送大小上限"):
        _reject_if_too_large(path, max_bytes=8)
    assert not path.exists()


def test_too_large_error_is_recognized() -> None:
    assert _is_too_large_error(BilibiliVideoDownloadError("视频超过发送大小上限"))
    assert not _is_too_large_error(BilibiliVideoDownloadError("当前视频无 DASH 流"))


def test_pick_request_qn_caps_to_prefer() -> None:
    assert pick_request_qn([16, 32, 64, 80, 112], 64) == 64
    assert pick_request_qn([16, 32], 80) == 32
    assert pick_request_qn(None, 64) == 64


def test_pick_request_qn_falls_back_to_lowest_when_all_above_prefer() -> None:
    assert pick_request_qn([80, 112], 64) == 80


def test_select_dash_streams_prefers_h264_same_qn() -> None:
    play = {
        "dash": {
            "video": [
                {"id": 64, "codecid": 12, "baseUrl": "https://v.hevc"},
                {"id": 64, "codecid": 7, "baseUrl": "https://v.avc"},
                {"id": 80, "codecid": 7, "baseUrl": "https://v.1080"},
            ],
            "audio": [
                {"id": 30216, "baseUrl": "https://a.low"},
                {"id": 30280, "baseUrl": "https://a.high"},
            ],
        }
    }
    video, audio = select_dash_streams(play, prefer_qn=64)
    assert video["codecid"] == 7
    assert video["id"] == 64
    assert audio["id"] == 30280


def test_select_dash_streams_picks_lowest_when_all_above_prefer() -> None:
    play = {
        "dash": {
            "video": [
                {"id": 112, "codecid": 7, "baseUrl": "https://v.hi"},
                {"id": 80, "codecid": 7, "baseUrl": "https://v.mid"},
            ],
            "audio": [{"id": 30280, "baseUrl": "https://a.high"}],
        }
    }
    video, _audio = select_dash_streams(play, prefer_qn=64)
    assert video["id"] == 80


def test_select_dash_streams_requires_dash() -> None:
    with pytest.raises(BilibiliVideoDownloadError):
        select_dash_streams({}, prefer_qn=64)


@pytest.mark.asyncio
async def test_download_cleans_owned_temp_dir_on_failure(tmp_path: Path) -> None:
    session = AsyncMock()
    created: list[Path] = []

    def fake_mkdtemp(prefix: str = "") -> str:
        path = tmp_path / f"{prefix}test"
        path.mkdir()
        created.append(path)
        return str(path)

    with (
        patch(
            "utils.bilibili_api.video_download.tempfile.mkdtemp",
            side_effect=fake_mkdtemp,
        ),
        patch(
            "utils.bilibili_api.video_download.fetch_playurl",
            AsyncMock(side_effect=BilibiliVideoDownloadError("boom")),
        ),
    ):
        with pytest.raises(BilibiliVideoDownloadError, match="boom"):
            await download_bilibili_video(session, bvid="BV1xx411c7mD", cid=1)

    assert created
    assert not created[0].exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("owned", [False, True])
async def test_cancel_download_cleans_partial_file_and_owned_directory(
    tmp_path, monkeypatch, owned
):
    from utils.bilibili_api import video_download

    work = tmp_path / ("bilibili_owned" if owned else "shared")
    work.mkdir()
    monkeypatch.setattr(video_download.tempfile, "mkdtemp", lambda **_: str(work))
    started = asyncio.Event()

    async def partial_download(_session, *, final, **kwargs):
        final.write_bytes(b"partial-video")
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        video_download, "_download_bilibili_video_into", partial_download
    )
    task = asyncio.create_task(
        download_bilibili_video(
            AsyncMock(),
            bvid="BV1xx411c7mD",
            cid=1,
            output_dir=None if owned else work,
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not list(tmp_path.rglob("*.mp4*"))
    assert work.exists() is not owned


@pytest.mark.asyncio
async def test_cancel_merge_kills_and_waits_for_subprocess(tmp_path, monkeypatch):
    from utils.bilibili_api import video_download

    create = asyncio.create_subprocess_exec
    process = None
    started = asyncio.Event()

    async def sleeping_process(*args, **kwargs):
        nonlocal process
        process = await create(
            sys.executable, "-c", "import time; time.sleep(60)", **kwargs
        )
        started.set()
        return process

    monkeypatch.setattr(video_download.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(
        video_download.asyncio, "create_subprocess_exec", sleeping_process
    )
    task = asyncio.create_task(
        _merge_av(tmp_path / "a", tmp_path / "v", tmp_path / "final.mp4")
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process is not None and process.returncode is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["durl", "dash_video", "dash_audio"])
@pytest.mark.parametrize("owned", [False, True])
async def test_cancel_http_stream_cleans_all_bilibili_files(
    tmp_path, monkeypatch, mode, owned
):
    from utils.bilibili_api import video_download

    monkeypatch.setattr(
        video_download,
        "fetch_playurl",
        AsyncMock(
            return_value={"durl": [{"url": "https://video"}]}
            if mode == "durl"
            else {
                "dash": {
                    "video": [{"id": 64, "codecid": 7, "baseUrl": "https://video"}],
                    "audio": [{"id": 30280, "baseUrl": "https://audio"}],
                },
            }
        ),
    )
    monkeypatch.setattr(video_download.shutil, "which", lambda _: "ffmpeg")
    started = asyncio.Event()

    async def stream(url):
        yield b"partial"
        if url == ("https://audio" if mode == "dash_audio" else "https://video"):
            started.set()
            await asyncio.Event().wait()

    def get_response(url, **kwargs):
        response = SimpleNamespace(
            status=200,
            content_length=None,
            content=SimpleNamespace(
                iter_chunked=lambda _: stream(url),
            ),
        )
        context = MagicMock()
        context.__aenter__.return_value = response
        context.__aexit__.return_value = False
        return context

    session = MagicMock()
    session.get.side_effect = get_response
    work = tmp_path / ("bilibili_owned" if owned else "shared")
    monkeypatch.setattr(video_download.tempfile, "mkdtemp", lambda **_: str(work))
    task = asyncio.create_task(
        download_bilibili_video(
            session, bvid="BV1xx411c7mD", cid=1, output_dir=None if owned else work
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]
    assert work.exists() is not owned
