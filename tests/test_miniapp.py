"""Tests for plugins.bilibili_link_parser.miniapp (direct module load)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MINIAPP_PATH = _ROOT / "plugins" / "bilibili_link_parser" / "miniapp.py"
_spec = importlib.util.spec_from_file_location(
    "bilibili_link_parser_miniapp", _MINIAPP_PATH
)
assert _spec is not None and _spec.loader is not None
miniapp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(miniapp)

normalize_bilibili_url = miniapp.normalize_bilibili_url
extract_bilibili_miniapp_urls = miniapp.extract_bilibili_miniapp_urls
parse_json_segment_data = miniapp.parse_json_segment_data


def test_normalize_bilibili_url_bvid() -> None:
    assert normalize_bilibili_url("BV1GJ411x7h7") == "BV1GJ411x7h7"


def test_normalize_bilibili_url_https() -> None:
    url = "https://www.bilibili.com/video/BV1GJ411x7h7"
    assert normalize_bilibili_url(url) == url


def test_normalize_bilibili_url_b23_without_scheme() -> None:
    assert normalize_bilibili_url("b23.tv/abc123") == "https://b23.tv/abc123"


def test_normalize_bilibili_url_empty() -> None:
    assert normalize_bilibili_url("") is None
    assert normalize_bilibili_url("   ") is None


def test_parse_json_segment_data_nested_string() -> None:
    payload = parse_json_segment_data('{"app":"com.tencent.miniapp_01"}')
    assert payload == {"app": "com.tencent.miniapp_01"}


def test_extract_bilibili_miniapp_urls_from_share_card() -> None:
    payload = {
        "app": "com.tencent.miniapp_01",
        "prompt": "[QQ小程序]哔哩哔哩",
        "meta": {
            "detail_1": {
                "appid": "1109937557",
                "title": "哔哩哔哩",
                "qqdocurl": "https://www.bilibili.com/video/BV1GJ411x7h7",
            }
        },
    }
    urls = extract_bilibili_miniapp_urls(payload)
    assert urls == ["https://www.bilibili.com/video/BV1GJ411x7h7"]
