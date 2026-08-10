"""Tests for x_monitor reply_batches ordering."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from nonebot.adapters.onebot.v11.message import Message, MessageSegment

ROOT = Path(__file__).resolve().parents[1]


def _ensure_package(name: str, path: Path) -> types.ModuleType:
    if name in sys.modules:
        module = sys.modules[name]
        if not getattr(module, "__path__", None):
            module.__path__ = [str(path)]
        return module
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


def _load_module(qualified_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(qualified_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _load_sender():
    _ensure_package("plugins", ROOT / "plugins")
    _ensure_package("plugins.x_monitor", ROOT / "plugins" / "x_monitor")
    # delivery_retry first so relative import resolves
    _load_module(
        "plugins.x_monitor.delivery_retry",
        ROOT / "plugins" / "x_monitor" / "delivery_retry.py",
    )
    return _load_module(
        "plugins.x_monitor.sender",
        ROOT / "plugins" / "x_monitor" / "sender.py",
    )


def test_reply_batches_preserves_interleaved_video_image_order(tmp_path: Path):
    """video, image, video 不得重排成 video, video, image。"""
    sender = _load_sender()
    v1 = tmp_path / "1.mp4"
    v2 = tmp_path / "2.mp4"
    img = tmp_path / "a.jpg"
    v1.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    v2.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    img.write_bytes(b"fakepng")

    msg = Message(
        [
            MessageSegment.video(v1.resolve()),
            MessageSegment.image(img.resolve()),
            MessageSegment.video(v2.resolve()),
        ]
    )
    batches = sender.reply_batches(msg)
    assert [[seg.type for seg in batch] for batch in batches] == [
        ["video"],
        ["image"],
        ["video"],
    ]


def test_reply_batches_keeps_trailing_text_after_videos(tmp_path: Path):
    sender = _load_sender()
    video = tmp_path / "1.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    msg = Message(
        [
            MessageSegment.text("leading"),
            MessageSegment.video(video.resolve()),
            MessageSegment.text("https://x.com/a/status/1"),
        ]
    )
    batches = sender.reply_batches(msg)
    assert len(batches) == 3
    assert batches[0].extract_plain_text() == "leading"
    assert batches[1][0].type == "video"
    assert batches[2].extract_plain_text() == "https://x.com/a/status/1"
