"""Tests for douyin_link_parser message builders."""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SENDER_PATH = _ROOT / "plugins" / "douyin_link_parser" / "sender.py"
_spec = importlib.util.spec_from_file_location(
    "douyin_link_parser_sender", _SENDER_PATH
)
assert _spec and _spec.loader
_sender = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sender)


def test_video_parts_uses_base64_not_file_uri(tmp_path: Path):
    video = tmp_path / "clip.mp4"
    payload = b"\x00\x00\x00\x18ftypmp42fake"
    video.write_bytes(payload)

    parts = list(_sender._video_parts(video))
    assert len(parts) == 1
    seg = parts[0]
    assert seg.type == "video"
    file_val = str(seg.data["file"])
    assert file_val.startswith("base64://")
    assert not file_val.startswith("file://")
    assert base64.b64decode(file_val.removeprefix("base64://")) == payload


def test_video_parts_missing_or_empty(tmp_path: Path):
    assert list(_sender._video_parts(tmp_path / "missing.mp4")) == []
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    assert list(_sender._video_parts(empty)) == []


def test_raw_max_bytes_fits_napcat_ws_after_base64():
    from utils.douyin_api.download import DEFAULT_MAX_BYTES

    # NapCat reverse-WS 默认约 100 MiB；base64 长度 = 4 * ceil(n/3)
    napcat_ceiling = 100 * 1024 * 1024
    encoded = 4 * ((DEFAULT_MAX_BYTES + 2) // 3)
    framing_headroom = 5 * 1024 * 1024
    assert encoded + framing_headroom <= napcat_ceiling
