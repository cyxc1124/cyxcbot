"""resolve_and_download must not leak owned temp dirs on download failure."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.douyin_api.resolve import DouyinResolveError, resolve_and_download


@pytest.mark.asyncio
async def test_resolve_cleans_owned_temp_when_all_downloads_fail(tmp_path: Path):
    detail = {
        "aweme_id": "1234567890",
        "desc": "unit test",
        "author": {"nickname": "tester"},
        "share_info": {"share_url": "https://www.douyin.com/video/1234567890"},
        "video": {
            "play_addr": {
                "url_list": ["https://cdn.example/video.mp4"],
            }
        },
    }

    created_dirs: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def tracking_mkdtemp(*args, **kwargs):
        path = real_mkdtemp(*args, **kwargs)
        created_dirs.append(Path(path))
        return path

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.resolve_short_url = AsyncMock(
        return_value="https://www.douyin.com/video/1234567890"
    )
    client.get_video_detail = AsyncMock(return_value=detail)
    client.get_session = AsyncMock(return_value=MagicMock())

    with (
        patch(
            "utils.douyin_api.resolve.tempfile.mkdtemp", side_effect=tracking_mkdtemp
        ),
        patch("utils.douyin_api.resolve.DouyinAPIClient", return_value=client),
        patch(
            "utils.douyin_api.resolve.build_video_url_candidates",
            return_value=[("https://cdn.example/video.mp4", {})],
        ),
        patch(
            "utils.douyin_api.resolve.download_file",
            new=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(DouyinResolveError, match="视频下载失败"):
            await resolve_and_download(
                "https://v.douyin.com/AbCdEf/",
                cookie_header="",
            )

    assert created_dirs, "expected mkdtemp to run"
    for directory in created_dirs:
        assert not directory.exists(), f"leaked temp dir: {directory}"


@pytest.mark.asyncio
async def test_resolve_keeps_temp_on_success_for_caller_cleanup(tmp_path: Path):
    detail = {
        "aweme_id": "1234567890",
        "desc": "unit test",
        "author": {"nickname": "tester"},
        "share_info": {"share_url": "https://www.douyin.com/video/1234567890"},
        "video": {
            "play_addr": {
                "url_list": ["https://cdn.example/video.mp4"],
            }
        },
    }
    work_dir = tmp_path / "caller_owned"
    work_dir.mkdir()
    save_path = work_dir / "1234567890.mp4"

    async def fake_download(url, path, session, **kwargs):
        path.write_bytes(b"fake-mp4")
        return True

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get_video_detail = AsyncMock(return_value=detail)
    client.get_session = AsyncMock(return_value=MagicMock())

    with (
        patch("utils.douyin_api.resolve.DouyinAPIClient", return_value=client),
        patch(
            "utils.douyin_api.resolve.build_video_url_candidates",
            return_value=[("https://cdn.example/video.mp4", {})],
        ),
        patch(
            "utils.douyin_api.resolve.download_file",
            new=AsyncMock(side_effect=fake_download),
        ),
    ):
        result = await resolve_and_download(
            "https://www.douyin.com/video/1234567890",
            cookie_header="",
            tmp_dir=work_dir,
        )

    assert result.file_path == save_path
    assert save_path.exists()
    assert work_dir.exists()
