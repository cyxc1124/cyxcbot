"""Official QQ Douyin pipeline: native events, budget, and local-media cleanup."""

import ast
import asyncio
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupAtMessageCreateEvent
from PIL import Image

from shared.adapter import outbound
from shared.adapter.bots import is_official_qq_bot
from shared.adapter.inbound import group_id_of, is_group_event, user_id_of
from shared.adapter.official_runtime import _bot_info
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.message_templates import DouyinLinkMessageTemplates
from utils.douyin_api import DouyinResolveError
from utils.douyin_api.resolve import DouyinMediaItem, DouyinVideoResult

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/douyin_link_parser"


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"douyin_official_{name}", PLUGIN / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize("kind", ["video", "album", "live", "large", "many_live"])
@pytest.mark.parametrize("reject", [False, True])
async def test_native_douyin_reply_and_cleanup(
    scope, kind, reject, tmp_path, monkeypatch
):
    sender, text, official, results = (
        _load(name)
        for name in ("sender", "message_text", "official_reply", "send_result")
    )
    cls = GroupAtMessageCreateEvent if scope == "group" else C2CMessageCreateEvent
    event = cls.model_validate(
        {
            "id": "incoming",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": "https://www.douyin.com/video/200",
            **(
                {"group_id": "g", "group_openid": "g-openid"}
                if scope == "group"
                else {}
            ),
            "author": {
                "id": "u",
                "user_openid": "u-openid",
                "member_openid": "u-openid",
                "member_role": "member",
                "bot": False,
            },
        }
    )
    assert "douyin.com/video/200" in text.collect_message_text(event)
    count = (
        26
        if kind == "large"
        else 8
        if kind == "many_live"
        else 2
        if kind == "live"
        else 1
    )
    items, paths = [], []
    for i in range(count):
        video = kind in {"video", "many_live"} or kind == "live" and i == 1
        path = tmp_path / f"{i}.{'mp4' if video else 'jpg'}"
        if video:
            path.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
        else:
            Image.new("RGB", (60, 80), (i * 7 % 255, 80, 160)).save(path)
        paths.append(path)
        items.append(
            DouyinMediaItem(kind="video" if video else "image", file_path=path)
        )
    result = DouyinVideoResult(
        aweme_id="200",
        title="caption",
        author="Author",
        share_url="https://www.douyin.com/video/200",
        file_path=paths[0],
        detail={},
        content_type="video" if kind == "video" else "album",
        items=items,
    )
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock(
        side_effect=LoggedQQApiError(40034105, "无权限") if reject else None
    )
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    logger = MagicMock()
    namespace = {
        "is_official_qq_bot": is_official_qq_bot,
        "official_reply_remaining": outbound.official_reply_remaining,
        "OfficialReplyLimitError": outbound.OfficialReplyLimitError,
        "LoggedQQApiError": LoggedQQApiError,
        "user_id_of": user_id_of,
        "group_id_of": group_id_of,
        "is_group_event": is_group_event,
        "ensure_shared_media_dir": lambda _: tmp_path,
        "get_config_service": lambda: SimpleNamespace(
            get_snapshot=lambda: SimpleNamespace(link_parser_shared_media_dir="")
        ),
        "resolve_and_download": AsyncMock(return_value=result),
        "chmod_shared_media_file": lambda _: None,
        "_SEND_SEM": asyncio.Semaphore(1),
        "build_douyin_link_message": sender.build_douyin_link_message,
        "prepare_official_reply": official.prepare_official_reply,
        "reply_batches": sender.reply_batches,
        "send_event_message": outbound.send_event_message,
        "is_onebot_send_success": results.is_onebot_send_success,
        "DouyinResolveError": DouyinResolveError,
        "ActionFailed": ActionFailed,
        "logger": logger,
    }
    source = ast.parse((PLUGIN / "__init__.py").read_text())
    functions = [
        node
        for node in source.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name
        in {"_download_and_reply", "_cleanup_result_files", "_message_id_of"}
    ]
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    module = ast.fix_missing_locations(
        ast.Module(body=[future, *functions], type_ignores=[])
    )
    exec(compile(module, str(PLUGIN / "__init__.py"), "exec"), namespace)
    await namespace["_download_and_reply"](
        bot,
        event,
        SimpleNamespace(
            douyin_cookie="", message_templates=DouyinLinkMessageTemplates()
        ),
        event.content,
    )
    expected = (
        1
        if reject
        else (5 if scope == "group" else 4)
        if kind == "many_live"
        else 3
        if kind == "live"
        else 2
    )
    assert api.await_count == expected
    assert [call.kwargs["msg_seq"] for call in api.await_args_list] == list(
        range(1, expected + 1)
    )
    assert all(call.kwargs["msg_id"] == event.id for call in api.await_args_list)
    if not reject:
        caption = api.await_args_list[-1].kwargs["message"].extract_plain_text()
        assert "caption" in caption
        if kind == "large":
            assert "26 张静态图片" in caption
            segment = api.await_args_list[0].kwargs["message"][0]
            assert segment.type == "file_image"
            from io import BytesIO

            preview = Image.open(BytesIO(segment.data["content"]))
            assert preview.width == 1280 and preview.height == 2240
        if kind == "many_live":
            assert ("另有 4 项媒体" if scope == "group" else "另有 5 项媒体") in caption
    assert not any(path.exists() for path in paths)
    assert not list(tmp_path.glob("douyin_preview_*.jpg"))
    logger.error.assert_not_called()
    logger.opt.return_value.error.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_count", [1, 2])
async def test_cancelling_preview_waits_for_file_cleanup(
    cancel_count, tmp_path, monkeypatch
):
    import threading

    from nonebot.adapters.onebot.v11 import Message, MessageSegment

    module = _load("official_reply")
    started, release, completed = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    generated = tmp_path / "preview.jpg"

    def render(*args):
        started.set()
        release.wait(5)
        generated.write_bytes(b"preview")
        completed.set()
        return generated

    monkeypatch.setattr(module, "_album_preview", render)
    message = Message([MessageSegment.image(tmp_path / str(i)) for i in range(6)])
    task = asyncio.create_task(module.prepare_official_reply(message, 5, tmp_path))
    assert await asyncio.to_thread(started.wait, 5)
    for _ in range(cancel_count):
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.to_thread(completed.wait, 5)
    assert not generated.exists()
