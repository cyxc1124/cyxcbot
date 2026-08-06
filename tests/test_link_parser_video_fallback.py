"""B 站链接解析：视频发送失败时降级封面。"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nonebot.adapters.onebot.v11.exception import ActionFailed

from shared.config.message_templates import LinkMessageTemplates
from utils.bilibili_api import VideoInfo

_ROOT = Path(__file__).resolve().parents[1]
_PLUGIN_ROOT = _ROOT / "plugins" / "bilibili_link_parser"


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


def _load_module(qualified_name: str, filename: str):
    path = _PLUGIN_ROOT / filename
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(_PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


_ensure_package("plugins", _ROOT / "plugins")
_ensure_package("plugins.bilibili_link_parser", _PLUGIN_ROOT)
_load_module("plugins.bilibili_link_parser.send_result", "send_result.py")
_load_module("plugins.bilibili_link_parser.sender", "sender.py")
_mod = _load_module("plugins.bilibili_link_parser.video_send", "video_send.py")

all_sends_ok = _mod.all_sends_ok
any_send_ok = _mod.any_send_ok
send_video_with_cover_fallback = _mod.send_video_with_cover_fallback


def _sample_video() -> VideoInfo:
    return VideoInfo(
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


def test_send_success_helpers() -> None:
    assert all_sends_ok([{"message_id": 1}])
    assert not all_sends_ok([{"message_id": 1}, {"message_id": None}])
    assert any_send_ok([{"message_id": None}, {"message_id": 2}])
    assert not any_send_ok(None)


@pytest.mark.asyncio
async def test_video_send_action_failed_falls_back_to_cover(tmp_path: Path) -> None:
    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")

    calls: list[int] = []

    async def fake_send_batches(_bot, _event, batches):
        calls.append(len(batches))
        if len(calls) == 1:
            raise ActionFailed(retcode=1200, wording="路径不存在")
        return [{"message_id": 42}]

    with patch.object(_mod, "send_batches", side_effect=fake_send_batches):
        results = await send_video_with_cover_fallback(
            AsyncMock(),
            MagicMock(),
            video=_sample_video(),
            video_path=video_file,
            templates=LinkMessageTemplates(),
        )

    assert all_sends_ok(results)
    assert calls == [2, 1]  # 视频+封面两批失败后，再发仅封面一批
