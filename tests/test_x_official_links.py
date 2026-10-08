"""Native QQ events and replies for X links; network calls are mocked."""

import ast
import asyncio
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupAtMessageCreateEvent

from shared.adapter import outbound
from shared.adapter.bots import is_official_qq_bot
from shared.adapter.inbound import group_id_of, is_group_event, user_id_of
from shared.adapter.official_runtime import _bot_info
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.message_templates import XLinkMessageTemplates
from utils.x_api.models import TweetItem, TweetMediaItem

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/x_link_parser"


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"x_official_{name}", PLUGIN / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize("kind", ["image", "video", "large"])
async def test_native_x_link_reply_preserves_media_and_budget(
    scope, kind, tmp_path, monkeypatch
):
    sender, text, result = (
        _load(name) for name in ("sender", "message_text", "send_result")
    )
    event_type = (
        GroupAtMessageCreateEvent if scope == "group" else C2CMessageCreateEvent
    )
    event = event_type.model_validate(
        {
            "id": "incoming",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": "https://x.com/author/status/200",
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
    assert "x.com/author/status/200" in text.collect_message_text(event)
    paths, media = [], []
    for i in range(6 if kind == "large" else 1):
        path = tmp_path / f"{i}.{'mp4' if kind == 'video' else 'jpg'}"
        path.write_bytes(b"media" + bytes([i]))
        paths.append(path)
        media.append(
            TweetMediaItem(
                kind="video" if kind == "video" else "image", url="", file_path=path
            )
        )
    tweet = TweetItem(
        id="200",
        text="caption",
        created_at="",
        username="author",
        name="Author",
        url="https://x.com/author/status/200",
        media_items=media,
    )
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    session = SimpleNamespace(close=AsyncMock())
    client = SimpleNamespace(get_tweet_by_id=AsyncMock(return_value=tweet))
    logger = MagicMock()
    namespace = {
        "create_session": lambda _: session,
        "XApiClient": lambda *_: client,
        "extract_x_tweet_ids": AsyncMock(return_value=["200"]),
        "ensure_shared_media_dir": lambda _: tmp_path,
        "get_config_service": lambda: SimpleNamespace(
            get_snapshot=lambda: SimpleNamespace(link_parser_shared_media_dir="")
        ),
        "materialize_tweet_media": AsyncMock(return_value=paths),
        "chmod_shared_media_file": lambda _: None,
        "_SEND_SEM": asyncio.Semaphore(1),
        "build_x_link_message": sender.build_x_link_message,
        "reply_batches": sender.reply_batches,
        "official_reply_message": sender.official_reply_message,
        "send_event_message": outbound.send_event_message,
        "is_official_qq_bot": is_official_qq_bot,
        "is_onebot_send_success": result.is_onebot_send_success,
        "user_id_of": user_id_of,
        "group_id_of": group_id_of,
        "is_group_event": is_group_event,
        "cleanup_media_files": lambda files: [
            path.unlink(missing_ok=True) for path in files
        ],
        "logger": logger,
        "ActionFailed": ActionFailed,
        "LoggedQQApiError": LoggedQQApiError,
        "OfficialReplyLimitError": outbound.OfficialReplyLimitError,
        "OFFICIAL_REPLY_LIMIT": outbound.OFFICIAL_REPLY_LIMIT,
        "official_reply_remaining": outbound.official_reply_remaining,
        "MessageSegment": MessageSegment,
    }
    source = ast.parse((PLUGIN / "__init__.py").read_text())
    functions = [
        node
        for node in source.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_fetch_and_reply", "_message_id_of"}
    ]
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    module = ast.fix_missing_locations(
        ast.Module(body=[future, *functions], type_ignores=[])
    )
    exec(compile(module, str(PLUGIN / "__init__.py"), "exec"), namespace)
    await namespace["_fetch_and_reply"](
        bot,
        event,
        SimpleNamespace(
            x_proxy="", x_api_bearer="test", message_templates=XLinkMessageTemplates()
        ),
        event.content,
    )
    assert api.await_count == ((5 if scope == "group" else 4) if kind == "large" else 2)
    assert [call.kwargs["msg_seq"] for call in api.await_args_list] == list(
        range(1, api.await_count + 1)
    )
    assert all(call.kwargs["msg_id"] == event.id for call in api.await_args_list)
    assert api.await_args_list[0].kwargs["message"][0].type == (
        "file_video" if kind == "video" else "file_image"
    )
    if kind == "large":
        assert (
            "另有 2 项媒体" if scope == "group" else "另有 3 项媒体"
        ) in api.await_args_list[-1].kwargs["message"].extract_plain_text()
    assert all(not path.exists() for path in paths)
    session.close.assert_awaited_once()
    logger.error.assert_not_called()
