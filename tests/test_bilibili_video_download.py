"""Tests for Bilibili DASH stream selection (no network)."""

from __future__ import annotations

import pytest

from utils.bilibili_api.video_download import (
    BilibiliVideoDownloadError,
    pick_request_qn,
    select_dash_streams,
)


def test_pick_request_qn_caps_to_prefer() -> None:
    assert pick_request_qn([16, 32, 64, 80, 112], 64) == 64
    assert pick_request_qn([16, 32], 80) == 32
    assert pick_request_qn(None, 64) == 64


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


def test_select_dash_streams_requires_dash() -> None:
    with pytest.raises(BilibiliVideoDownloadError):
        select_dash_streams({}, prefer_qn=64)
