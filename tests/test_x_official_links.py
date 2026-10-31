"""Actual X handlers with native QQ events; external API calls are mocked."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupAtMessageCreateEvent
from nonebot.exception import IgnoredException

from shared.adapter import outbound
from shared.adapter.official_runtime import _bot_info
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.types import AppConfigSnapshot
from shared.config.x_link_parser_policy import (
    XLinkParserGroupPolicyRecord,
    XLinkParserUserPolicyRecord,
)
from tests.test_config_service_load_perf import _ensure_real_db_modules
from utils.x_api.models import TweetItem, TweetMediaItem

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/x_link_parser"


def _load(name: str, path: Path, *, package: bool = False):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)] if package else None
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin(monkeypatch):
    _ensure_real_db_modules()
    monkeypatch.setattr(nonebot.get_driver(), "on_startup", lambda callback: callback)
    module = _load("_test_native_x_plugin", PLUGIN / "__init__.py", package=True)
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    monkeypatch.setattr(outbound, "_official_locks", {})
    monkeypatch.setattr(outbound, "_official_last_sent", {})
    monkeypatch.setattr(module, "logger", MagicMock())
    assert module.group_x_link_parser.handlers[0].call is module.handle_group_x_link
    assert module.private_x_link_parser.handlers[0].call is module.handle_private_x_link
    try:
        yield module
    finally:
        module.group_x_link_parser.destroy()
        module.private_x_link_parser.destroy()
        for name in list(sys.modules):
            if name in {
                "_test_native_x_plugin",
                "_test_x_group_guard",
                "_test_x_c2c_guard",
            } or name.startswith("_test_native_x_plugin."):
                del sys.modules[name]


def _event(scope: str, content: str = "https://x.com/author/status/200"):
    event_type = (
        GroupAtMessageCreateEvent if scope == "group" else C2CMessageCreateEvent
    )
    return event_type.model_validate(
        {
            "id": "incoming",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": content,
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


def _pipeline(plugin, scope, kind, tmp_path, monkeypatch, *, content=None):
    snap = AppConfigSnapshot(
        x_api_bearer="test-bearer",
        link_parser_shared_media_dir=str(tmp_path),
        message_enabled_group_ids=["g-openid"],
        message_enabled_user_ids=["u-openid"],
        x_link_parser_group_policies={
            "g-openid": XLinkParserGroupPolicyRecord("g-openid", True)
        },
        x_link_parser_user_policies={
            "u-openid": XLinkParserUserPolicyRecord("u-openid", True)
        },
    )
    svc = SimpleNamespace(
        get_snapshot=lambda: snap, register_reload_callback=MagicMock()
    )
    monkeypatch.setattr(plugin, "get_config_service", lambda: svc)
    monkeypatch.setattr("shared.config.service.get_config_service", lambda: svc)
    plugin.reload_config()
    paths, media = [], []
    for i in range(0 if kind == "text" else 6 if kind in {"large", "mixed"} else 1):
        media_kind = (
            "video" if kind == "video" or kind == "mixed" and i % 2 == 0 else "image"
        )
        path = tmp_path / f"{i}.{'mp4' if media_kind == 'video' else 'jpg'}"
        path.write_bytes(b"media" + bytes([i]))
        paths.append(path)
        media.append(TweetMediaItem(kind=media_kind, url="", file_path=path))
    tweet = TweetItem(
        id="200",
        text="caption",
        created_at="",
        username="author",
        name="Author",
        url="https://x.com/author/status/200",
        media_items=media,
    )
    session = SimpleNamespace(close=AsyncMock())
    client = SimpleNamespace(get_tweet_by_id=AsyncMock(return_value=tweet))
    create_session = MagicMock(return_value=session)
    client_factory = MagicMock(return_value=client)
    monkeypatch.setattr(plugin, "create_session", create_session)
    monkeypatch.setattr(plugin, "XApiClient", client_factory)
    monkeypatch.setattr(
        plugin, "materialize_tweet_media", AsyncMock(return_value=paths)
    )
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    event = _event(scope, content) if content else _event(scope)
    handler = (
        plugin.handle_group_x_link if scope == "group" else plugin.handle_private_x_link
    )
    return SimpleNamespace(
        snap=snap,
        svc=svc,
        tweet=tweet,
        bot=bot,
        api=api,
        event=event,
        handler=handler,
        session=session,
        client=client,
        paths=paths,
        create_session=create_session,
        client_factory=client_factory,
    )


@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize("kind", ["text", "image", "video", "large", "mixed"])
async def test_native_handler_preserves_media_and_reply_budget(
    plugin, scope, kind, tmp_path, monkeypatch
):
    pipe = _pipeline(plugin, scope, kind, tmp_path, monkeypatch)
    await pipe.handler(pipe.bot, pipe.event)
    expected = (
        (5 if scope == "group" else 4)
        if kind in {"large", "mixed"}
        else 1
        if kind == "text"
        else 2
    )
    assert pipe.api.await_count == expected
    assert [call.kwargs["msg_seq"] for call in pipe.api.await_args_list] == list(
        range(1, expected + 1)
    )
    assert all(
        call.kwargs["msg_id"] == pipe.event.id for call in pipe.api.await_args_list
    )
    caption = pipe.api.await_args_list[-1].kwargs["message"].extract_plain_text()
    assert "caption" in caption
    if kind != "text":
        media_calls = pipe.api.await_args_list[:-1]
        assert [call.kwargs["message"][0].type for call in media_calls] == [
            "file_video" if item.kind == "video" else "file_image"
            for item in pipe.tweet.media_items[: expected - 1]
        ]
        assert all(
            call.kwargs["message"][0].data["content"].startswith(b"media")
            for call in media_calls
        )
    if kind in {"large", "mixed"}:
        assert ("另有 2 项媒体" if scope == "group" else "另有 3 项媒体") in caption
    assert all(not path.exists() for path in pipe.paths)
    pipe.session.close.assert_awaited_once()
    pipe.client_factory.assert_called_once_with(pipe.session, "test-bearer")
    pipe.create_session.assert_called_once_with(pipe.snap.x_proxy)
    plugin.logger.opt.return_value.error.assert_not_called()


@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_native_handler_first_link_and_remaining_budget(
    plugin, scope, tmp_path, monkeypatch
):
    pipe = _pipeline(
        plugin,
        scope,
        "large",
        tmp_path,
        monkeypatch,
        content="https://x.com/author/status/200 https://twitter.com/author/status/201",
    )
    pipe.event._reply_seq = 3
    await pipe.handler(pipe.bot, pipe.event)
    pipe.client.get_tweet_by_id.assert_awaited_once_with("200")
    assert pipe.api.await_count == (2 if scope == "group" else 1)
    caption = pipe.api.await_args_list[-1].kwargs["message"].extract_plain_text()
    assert "仅解析首个 X 链接" in caption
    assert ("另有 5 项媒体" if scope == "group" else "另有 6 项媒体") in caption
    assert outbound.official_reply_remaining(pipe.event) == 0
    assert all(not path.exists() for path in pipe.paths)


@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_native_handler_leaf_disabled_and_bearer_missing_do_not_fetch(
    plugin, scope, tmp_path, monkeypatch
):
    pipe = _pipeline(plugin, scope, "text", tmp_path, monkeypatch)
    pipe.snap.x_link_parser_group_policies.clear()
    pipe.snap.x_link_parser_user_policies.clear()
    await pipe.handler(pipe.bot, pipe.event)
    pipe.create_session.assert_not_called()
    pipe.snap.x_link_parser_group_policies["g-openid"] = XLinkParserGroupPolicyRecord(
        "g-openid", True
    )
    pipe.snap.x_link_parser_user_policies["u-openid"] = XLinkParserUserPolicyRecord(
        "u-openid", True
    )
    pipe.snap.x_api_bearer = ""
    await plugin._on_config_reload(pipe.snap)
    await pipe.handler(pipe.bot, pipe.event)
    pipe.create_session.assert_not_called()
    plugin._register_config_reload()
    pipe.svc.register_reload_callback.assert_called_once_with(plugin._on_config_reload)


@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_native_message_guard_blocks_before_leaf_handler(
    plugin, scope, tmp_path, monkeypatch
):
    pipe = _pipeline(plugin, scope, "text", tmp_path, monkeypatch)
    path = (
        ROOT
        / "plugins"
        / ("group_guard" if scope == "group" else "private_guard")
        / "__init__.py"
    )
    monkeypatch.setattr("nonebot.message.event_preprocessor", lambda callback: callback)
    guard = _load(f"_test_x_{scope}_guard", path)
    remember = AsyncMock()
    monkeypatch.setattr(guard, "remember_official_session", remember)
    pipe.snap.message_enabled_group_ids.clear()
    pipe.snap.message_enabled_user_ids.clear()
    block = (
        guard.block_disabled_group_messages
        if scope == "group"
        else guard.block_disabled_private_messages
    )
    with pytest.raises(IgnoredException):
        await block(pipe.event)
        await pipe.handler(pipe.bot, pipe.event)
    remember.assert_awaited_once_with(pipe.event)
    pipe.create_session.assert_not_called()


@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize(
    "error",
    [LoggedQQApiError(40034105, "无权限"), LoggedQQApiError(40034006, "消息内容违规")],
)
async def test_native_platform_rejection_cleans_media_without_stack(
    plugin, scope, error, tmp_path, monkeypatch
):
    pipe = _pipeline(plugin, scope, "image", tmp_path, monkeypatch)
    pipe.api.side_effect = error
    await pipe.handler(pipe.bot, pipe.event)
    pipe.api.assert_awaited_once()
    pipe.session.close.assert_awaited_once()
    assert all(not path.exists() for path in pipe.paths)
    plugin.logger.opt.return_value.error.assert_not_called()


@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_native_url_rejection_retries_text_without_url(
    plugin, scope, tmp_path, monkeypatch
):
    pipe = _pipeline(plugin, scope, "text", tmp_path, monkeypatch)
    accepted = []

    async def send(**kwargs):
        text = kwargs["message"].extract_plain_text()
        if "https://" in text:
            raise LoggedQQApiError(40054010, "不允许发送URL")
        accepted.append(kwargs)

    pipe.api.side_effect = send
    await pipe.handler(pipe.bot, pipe.event)
    assert pipe.api.await_count == 2 and len(accepted) == 1
    assert "caption" in accepted[0]["message"].extract_plain_text()
    assert accepted[0]["msg_id"] == pipe.event.id
    assert outbound.official_reply_remaining(pipe.event) == (
        4 if scope == "group" else 3
    )


@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_cancelled_native_send_stops_and_cleans_media(
    plugin, scope, tmp_path, monkeypatch
):
    pipe = _pipeline(plugin, scope, "mixed", tmp_path, monkeypatch)
    started = asyncio.Event()

    async def send(**kwargs):
        started.set()
        await asyncio.Event().wait()

    pipe.api.side_effect = send
    task = asyncio.create_task(pipe.handler(pipe.bot, pipe.event))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    pipe.api.assert_awaited_once()
    pipe.session.close.assert_awaited_once()
    assert all(not path.exists() for path in pipe.paths)
    assert not plugin._SEND_SEM.locked() and not plugin._PIPELINE_SEM.locked()
