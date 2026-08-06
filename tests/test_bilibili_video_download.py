"""Tests for Bilibili DASH stream selection (no network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from utils.bilibili_api.video_download import (
    DEFAULT_MAX_BYTES,
    BilibiliVideoDownloadError,
    download_bilibili_video,
    pick_request_qn,
    select_dash_streams,
)


def test_max_bytes_matches_llbot_raw_file_ceiling() -> None:
    """file:// 直读，上限对齐 LuckyLilliaBot SendElement.video 原始文件硬顶。"""
    assert DEFAULT_MAX_BYTES == 1024 * 1024 * 1024


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
