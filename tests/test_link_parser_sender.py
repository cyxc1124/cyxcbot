"""Tests for bilibili_link_parser message builders."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from utils.bilibili_api import DynamicItem, VideoInfo

_ROOT = Path(__file__).resolve().parents[1]
_SENDER_PATH = _ROOT / "plugins" / "bilibili_link_parser" / "sender.py"
_spec = importlib.util.spec_from_file_location(
    "bilibili_link_parser_sender", _SENDER_PATH
)
assert _spec and _spec.loader
_sender = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sender)
build_dynamic_link_message = _sender.build_dynamic_link_message
build_video_link_message = _sender.build_video_link_message
reply_batches = _sender.reply_batches


def _sample_dynamic() -> DynamicItem:
    return DynamicItem(
        dynamic_id=1217074344495153155,
        uid=123,
        name="测试UP",
        timestamp=1710000000,
        dynamic_type=4,
        title="图文标题",
        body_text="正文摘要",
        images=["https://example.com/a.jpg", "https://example.com/b.jpg"],
    )


def test_build_dynamic_link_message_uses_screenshot_when_provided() -> None:
    msg = build_dynamic_link_message(
        _sample_dynamic(),
        screenshot_image=b"png-bytes",
        include_dynamic_media=False,
    )
    assert len(msg) >= 2
    assert msg[0].type == "image"
    assert "图文标题" in str(msg)


def test_build_dynamic_link_message_falls_back_to_api_images() -> None:
    msg = build_dynamic_link_message(
        _sample_dynamic(),
        include_dynamic_media=True,
    )
    image_segments = [seg for seg in msg if seg.type == "image"]
    assert len(image_segments) == 2
    assert "正文摘要" in str(msg)


def test_build_video_link_message_with_file_keeps_cover(
    tmp_path: Path,
) -> None:
    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    video = VideoInfo(
        aid=1,
        bvid="BV1xx411c7mD",
        title="测试视频",
        description="",
        cover="https://example.com/cover.jpg",
        duration=12,
        pub_date=1710000000,
        author_uid=1,
        author_name="UP",
        cid=100,
    )
    msg = build_video_link_message(video, video_path=video_file)
    video_seg = next(seg for seg in msg if seg.type == "video")
    file_ref = str(video_seg.data.get("file", ""))
    assert file_ref.startswith("file://"), file_ref
    assert "base64://" not in file_ref
    assert any(seg.type == "image" for seg in msg)
    batches = reply_batches(msg)
    assert len(batches) >= 2
    assert batches[0][0].type == "video"
    # 封面与文案可同条；video 单独一条
    cover_batch = next(b for b in batches if any(s.type == "image" for s in b))
    assert any(s.type == "image" for s in cover_batch)
    assert "测试视频" in str(cover_batch)
