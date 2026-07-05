"""Tests for bilibili_link_parser message builders."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SENDER_PATH = _ROOT / "plugins" / "bilibili_link_parser" / "sender.py"
_spec = importlib.util.spec_from_file_location("bilibili_link_parser_sender", _SENDER_PATH)
assert _spec and _spec.loader
_sender = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sender)
build_dynamic_link_message = _sender.build_dynamic_link_message

from utils.bilibili_api import DynamicItem


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
