"""Native QQ events through Bilibili policy, resolution, sending and cleanup."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from nonebot.adapters.onebot.v11 import Bot as OneBotBot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11 import Message as OneBotMessage
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupAtMessageCreateEvent
from nonebot.exception import IgnoredException

from shared.adapter import outbound
from shared.adapter.official_runtime import _bot_info
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.link_parser_policy import (
    LinkParserGroupPolicyRecord,
    LinkParserUserPolicyRecord,
)
from shared.config.types import AppConfigSnapshot
from utils.bilibili_api import (
    BilibiliVideoDownloadError,
    DynamicItem,
    RoomInfo,
    UserInfo,
    VideoInfo,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_plugin(name: str, directory: str):
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(sqlalchemy_database_url="sqlite+aiosqlite:///:memory:")
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    if name not in sys.modules:
        path = ROOT / "plugins" / directory
        spec = importlib.util.spec_from_file_location(
            name, path / "__init__.py", submodule_search_locations=[str(path)]
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _event(scope: str, content: str):
    cls = GroupAtMessageCreateEvent if scope == "group" else C2CMessageCreateEvent
    return cls.model_validate(
        {
            "id": "incoming",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": content,
            **(
                {"group_id": "g-openid", "group_openid": "g-openid"}
                if scope == "group"
                else {}
            ),
            "author": {
                "id": "u-openid",
                "user_openid": "u-openid",
                "member_openid": "u-openid",
                "member_role": "member",
                "bot": False,
            },
        }
    )


def _snapshot(*, parser_enabled=True, master_enabled=True):
    return AppConfigSnapshot(
        bilibili_cookie="test-cookie",
        message_enabled_group_ids=["g-openid"] if master_enabled else [],
        message_enabled_user_ids=["u-openid"] if master_enabled else [],
        link_parser_group_policies={
            "g-openid": LinkParserGroupPolicyRecord(
                group_id="g-openid",
                video_enabled=parser_enabled,
                live_enabled=parser_enabled,
                dynamic_enabled=parser_enabled,
                send_video_enabled=parser_enabled,
            )
        },
        link_parser_user_policies={
            "u-openid": LinkParserUserPolicyRecord(
                user_id="u-openid",
                video_enabled=parser_enabled,
                live_enabled=parser_enabled,
                dynamic_enabled=parser_enabled,
                send_video_enabled=parser_enabled,
            )
        },
    )


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    plugin = _load_plugin("bilibili_native_test", "bilibili_link_parser")
    monkeypatch.setattr(
        sys.modules[f"{plugin.__name__}.page_selection"], "_pending", {}
    )
    snapshot = _snapshot()
    snapshot.link_parser_shared_media_dir = str(tmp_path)
    service = SimpleNamespace(get_snapshot=lambda: snapshot)
    monkeypatch.setattr(plugin, "get_config_service", lambda: service)
    monkeypatch.setattr("shared.config.service.get_config_service", lambda: service)
    plugin.reload_config()
    video = VideoInfo(
        aid=1,
        bvid="BV1xx411c7mD",
        title="视频标题",
        description="",
        cover="https://example.com/cover.jpg",
        duration=12,
        pub_date=1710000000,
        author_uid=1,
        author_name="UP",
        cid=100,
    )
    video_manager = SimpleNamespace(
        init=AsyncMock(),
        api=SimpleNamespace(session=MagicMock()),
        get_video_detail=AsyncMock(return_value=video),
    )
    monkeypatch.setattr(plugin, "video_api_manager", video_manager)
    room = RoomInfo.from_api_data(
        {
            "room_id": 1,
            "uid": 1,
            "title": "直播标题",
            "cover": "https://example.com/live.jpg",
        }
    )
    live_manager = SimpleNamespace(
        init=AsyncMock(),
        get_room_and_user_info=AsyncMock(
            return_value=(room, UserInfo(uid=1, name="主播", face=""))
        ),
    )
    monkeypatch.setattr(plugin, "live_api_manager", live_manager)
    dynamic = DynamicItem(
        dynamic_id=123456789,
        uid=1,
        name="UP",
        timestamp=1710000000,
        dynamic_type=4,
        title="动态标题",
        body_text="动态正文",
        images=[f"https://example.com/{i}.jpg" for i in range(7)],
    )
    monkeypatch.setattr(
        plugin,
        "DynamicFetcher",
        lambda *_: SimpleNamespace(
            fetch_dynamic_detail=AsyncMock(return_value=dynamic),
        ),
    )
    monkeypatch.setattr(
        plugin, "get_dynamic_screenshot", AsyncMock(return_value=(b"png", None, None))
    )
    materialize = outbound._materialize_media

    async def local_media(value):
        if str(value).startswith("https://example.com/"):
            return b"image-bytes"
        return await materialize(value)

    monkeypatch.setattr(outbound, "_materialize_media", local_media)
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    return plugin, snapshot, video_manager


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize(
    "kind",
    [
        "video",
        "download_failure",
        "live",
        "dynamic",
        "screenshot",
        "screenshot_failure",
    ],
)
async def test_actual_native_handler_policy_resolution_and_reply(
    scope, kind, pipeline, tmp_path, monkeypatch
):
    plugin, snapshot, video_manager = pipeline
    content = {
        "video": "BV1xx411c7mD",
        "download_failure": "BV1xx411c7mD",
        "live": "https://live.bilibili.com/1",
        "dynamic": "https://t.bilibili.com/123456789",
        "screenshot": "https://www.bilibili.com/opus/123456789",
        "screenshot_failure": "https://www.bilibili.com/opus/123456789",
    }[kind]
    event = _event(scope, content)
    snapshot.dynamic_enable_screenshot = kind in {"screenshot", "screenshot_failure"}
    if kind == "screenshot_failure":
        monkeypatch.setattr(
            plugin,
            "get_dynamic_screenshot",
            AsyncMock(return_value=(None, "browser unavailable", None)),
        )
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    download = AsyncMock(
        side_effect=BilibiliVideoDownloadError("download rejected")
        if kind == "download_failure"
        else None,
        return_value=video_path,
    )
    monkeypatch.setattr(plugin, "download_bilibili_video", download)
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    handler = (
        plugin.handle_group_link if scope == "group" else plugin.handle_private_link
    )
    await handler(bot, event)

    expected = (
        (5 if scope == "group" else 4)
        if kind in {"dynamic", "screenshot_failure"}
        else 3
        if kind == "video"
        else 2
    )
    assert api.await_count == expected
    assert [call.kwargs["msg_seq"] for call in api.await_args_list] == list(
        range(1, expected + 1)
    )
    assert all(call.kwargs["msg_id"] == event.id for call in api.await_args_list)
    messages = [call.kwargs["message"] for call in api.await_args_list]
    caption = messages[-1].extract_plain_text()
    assert {
        "video": "视频标题",
        "download_failure": "视频标题",
        "live": "直播标题",
        "dynamic": "动态标题",
        "screenshot": "动态标题",
        "screenshot_failure": "动态标题",
    }[kind] in caption
    assert "bilibili.com" in caption
    assert all(
        message[0].type in {"file_image", "file_video"} for message in messages[:-1]
    )
    if kind in {"dynamic", "screenshot_failure"}:
        assert f"另有 {7 - expected + 1} 项媒体" in caption
    if kind == "screenshot":
        assert messages[0][0].data["content"] == b"png"
    if kind == "video":
        assert messages[0][0].type == "file_video"
        assert not video_path.exists()
        download.assert_awaited_once()
    video_manager.init.assert_awaited_once_with("test-cookie")


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_native_default_parser_off_and_master_guard_off(
    scope, pipeline, monkeypatch
):
    plugin, snapshot, video_manager = pipeline
    event = _event(scope, "BV1xx411c7mD")
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    snapshot.link_parser_group_policies.clear()
    snapshot.link_parser_user_policies.clear()
    await (
        plugin.handle_group_link if scope == "group" else plugin.handle_private_link
    )(bot, event)
    video_manager.init.assert_not_awaited()
    guard = _load_plugin(
        f"bilibili_native_{scope}_guard",
        "group_guard" if scope == "group" else "private_guard",
    )
    monkeypatch.setattr(guard, "remember_official_session", AsyncMock())
    snapshot.message_enabled_group_ids.clear()
    snapshot.message_enabled_user_ids.clear()
    with pytest.raises(IgnoredException):
        await (
            guard.block_disabled_group_messages
            if scope == "group"
            else guard.block_disabled_private_messages
        )(event)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize("failure", ["media", "cover", "permission", "url", "cancel"])
async def test_native_rejection_or_cancellation_cleans_video(
    scope, failure, pipeline, tmp_path, monkeypatch
):
    plugin, _, _ = pipeline
    event = _event(scope, "BV1xx411c7mD")
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"video")
    monkeypatch.setattr(plugin, "download_bilibili_video", AsyncMock(return_value=path))
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    calls = []

    async def api(**kwargs):
        message = kwargs["message"]
        calls.append(message)
        if failure == "cancel":
            raise asyncio.CancelledError
        if failure == "media" and message[0].type == "file_video":
            raise LoggedQQApiError(40034004, "转存失败")
        if failure == "cover" and message[0].type == "file_image":
            raise LoggedQQApiError(304080, "文件信息无效")
        if failure == "permission":
            raise LoggedQQApiError(40034105, "无权限")
        if failure == "url" and "https://" in message.extract_plain_text():
            raise LoggedQQApiError(40054010, "不允许发送URL")

    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    handler = (
        plugin.handle_group_link if scope == "group" else plugin.handle_private_link
    )
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await handler(bot, event)
    elif failure == "permission":
        await handler(bot, event)
        assert len(calls) == 1
    else:
        await handler(bot, event)
        assert "视频标题" in calls[-1].extract_plain_text()
        assert sum(message[0].type == "file_video" for message in calls) == 1
        if failure == "url":
            assert len(calls) == 4
            assert "https://" not in calls[-1].extract_plain_text()
    assert not path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_native_remaining_budget_reserves_caption(scope, pipeline, monkeypatch):
    plugin, snapshot, _ = pipeline
    event = _event(scope, "https://t.bilibili.com/123456789")
    event._reply_seq = 3
    snapshot.dynamic_enable_screenshot = False
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    await (
        plugin.handle_group_link if scope == "group" else plugin.handle_private_link
    )(bot, event)
    assert api.await_count == (2 if scope == "group" else 1)
    assert "动态标题" in api.await_args_list[-1].kwargs["message"].extract_plain_text()
    assert outbound.official_reply_remaining(event) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_exhausted_native_event_skips_resolution_and_media(
    scope, pipeline, monkeypatch
):
    plugin, _, video_manager = pipeline
    event = _event(scope, "BV1xx411c7mD")
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    while outbound.official_reply_remaining(event):
        await outbound.send_event_message(bot, event, plugin.Message("earlier reply"))
    assert event._reply_seq == (5 if scope == "group" else 4)
    api.reset_mock()
    resolve = AsyncMock(wraps=plugin._resolve_reply)
    download, mux, send = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(plugin, "_resolve_reply", resolve)
    monkeypatch.setattr(plugin, "download_bilibili_video", download)
    monkeypatch.setattr("utils.bilibili_api.video_download._merge_av", mux)
    monkeypatch.setattr("bilibili_native_test.video_send.send_event_message", send)

    await (
        plugin.handle_group_link if scope == "group" else plugin.handle_private_link
    )(bot, event)

    resolve.assert_not_awaited()
    video_manager.init.assert_not_awaited()
    video_manager.get_video_detail.assert_not_awaited()
    plugin.live_api_manager.init.assert_not_awaited()
    download.assert_not_awaited()
    mux.assert_not_awaited()
    send.assert_not_awaited()
    api.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_single_native_reply_budget_skips_video_download(
    scope, pipeline, monkeypatch
):
    plugin, _, video_manager = pipeline
    event = _event(scope, "BV1xx411c7mD")
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    while outbound.official_reply_remaining(event) > 1:
        await outbound.send_event_message(bot, event, plugin.Message("earlier reply"))
    api.reset_mock()
    download, mux = AsyncMock(), AsyncMock()
    monkeypatch.setattr(plugin, "download_bilibili_video", download)
    monkeypatch.setattr("utils.bilibili_api.video_download._merge_av", mux)

    await (
        plugin.handle_group_link if scope == "group" else plugin.handle_private_link
    )(bot, event)

    video_manager.get_video_detail.assert_awaited_once()
    download.assert_not_awaited()
    mux.assert_not_awaited()
    api.assert_awaited_once()
    assert "视频标题" in api.await_args.kwargs["message"].extract_plain_text()
    assert outbound.official_reply_remaining(event) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_single_native_reply_budget_skips_dynamic_screenshot(
    scope, pipeline, monkeypatch
):
    plugin, snapshot, _ = pipeline
    assert snapshot.dynamic_enable_screenshot is True
    event = _event(scope, "https://t.bilibili.com/123456789")
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    api = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    while outbound.official_reply_remaining(event) > 1:
        await outbound.send_event_message(bot, event, plugin.Message("earlier reply"))
    api.reset_mock()

    await (
        plugin.handle_group_link if scope == "group" else plugin.handle_private_link
    )(bot, event)

    plugin.get_dynamic_screenshot.assert_not_called()
    api.assert_awaited_once()
    caption = api.await_args.kwargs["message"].extract_plain_text()
    assert "动态标题" in caption and "动态正文" in caption
    assert snapshot.dynamic_enable_screenshot is True
    assert outbound.official_reply_remaining(event) == 0


@pytest.fixture(params=["group", "c2c", "onebot_group", "onebot_private"])
def page_client(request, pipeline, monkeypatch, tmp_path):
    plugin, snapshot, manager = pipeline
    video = manager.get_video_detail.return_value
    video.pages = VideoInfo.from_api_data(
        {
            "pages": [
                {"cid": 100, "part": "开场", "duration": 10},
                {"cid": 200, "part": "正式内容", "duration": 20},
                {"cid": 300, "part": "问答", "duration": 30},
            ]
        }
    ).pages
    scope = request.param
    group = scope in {"group", "onebot_group"}
    api = AsyncMock(return_value={"message_id": 42})
    adapter = MagicMock()
    if scope.startswith("onebot"):
        adapter.get_name.return_value = "OneBot V11"
        bot = OneBotBot(adapter, "1")
        snapshot.message_enabled_group_ids.append("456")
        snapshot.message_enabled_user_ids.append("123")
        snapshot.link_parser_group_policies["456"] = LinkParserGroupPolicyRecord(
            group_id="456", video_enabled=True, send_video_enabled=True
        )
        snapshot.link_parser_user_policies["123"] = LinkParserUserPolicyRecord(
            user_id="123", video_enabled=True, send_video_enabled=True
        )
        monkeypatch.setattr(bot, "send_group_msg" if group else "send_private_msg", api)

        def event(content):
            cls = GroupMessageEvent if group else PrivateMessageEvent
            return cls.model_validate(
                {
                    "time": 1,
                    "self_id": 1,
                    "post_type": "message",
                    "message_type": "group" if group else "private",
                    "sub_type": "normal" if group else "friend",
                    "user_id": 123,
                    **({"group_id": 456} if group else {}),
                    "message_id": 1,
                    "message": OneBotMessage(content),
                    "raw_message": content,
                    "font": 0,
                    "sender": {"user_id": 123},
                }
            )

    else:
        adapter.get_name.return_value = "QQ"
        bot = QQBot(adapter, "app", _bot_info("app", "secret", False))
        monkeypatch.setattr(bot, "send_to_group" if group else "send_to_c2c", api)

        def event(content):
            return _event(scope, content)

    path = tmp_path / "page.mp4"
    path.write_bytes(b"video")
    download = AsyncMock(return_value=path)
    monkeypatch.setattr(plugin, "download_bilibili_video", download)
    return SimpleNamespace(
        plugin=plugin,
        snapshot=snapshot,
        manager=manager,
        video=video,
        bot=bot,
        api=api,
        event=event,
        handler=plugin.handle_group_link if group else plugin.handle_private_link,
        download=download,
        path=path,
        selections=sys.modules[f"{plugin.__name__}.page_selection"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["video", "card", "download_failure"])
async def test_page_menu_and_numeric_choice(page_client, mode):
    c = page_client
    if mode == "card":
        for policies in (
            c.snapshot.link_parser_group_policies,
            c.snapshot.link_parser_user_policies,
        ):
            for key, policy in policies.items():
                policies[key] = replace(policy, send_video_enabled=False)
    elif mode == "download_failure":
        c.download.side_effect = BilibiliVideoDownloadError("download rejected")
    await c.handler(c.bot, c.event(c.video.bvid))
    c.api.assert_awaited_once()
    menu = c.api.await_args.kwargs["message"].extract_plain_text()
    assert "P1 开场\nP2 正式内容\nP3 问答" in menu
    assert "5 分钟" in menu and "1～3" in menu
    c.download.assert_not_awaited()
    c.api.reset_mock()

    await c.handler(c.bot, c.event(" 2 "))
    caption = c.api.await_args.kwargs["message"].extract_plain_text()
    assert "P2 正式内容" in caption and "?p=2" in caption
    assert c.video.cid == 100 and c.video.page is None
    c.manager.get_video_detail.assert_awaited_once()
    if mode == "card":
        c.download.assert_not_awaited()
    else:
        assert c.download.await_args.kwargs["cid"] == 200
    if mode == "video":
        assert not c.path.exists()
    c.api.reset_mock()
    await c.handler(c.bot, c.event("2"))
    c.api.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "choice", ["0", "4", "9" * 5000], ids=["zero", "out-of-range", "huge"]
)
async def test_invalid_page_choice_can_retry(page_client, choice):
    c = page_client
    await c.handler(c.bot, c.event(c.video.bvid))
    await c.handler(c.bot, c.event(choice))
    assert "1～3" in c.api.await_args.kwargs["message"].extract_plain_text()
    c.download.assert_not_awaited()
    await c.handler(c.bot, c.event("3"))
    assert c.download.await_args.kwargs["cid"] == 300


@pytest.mark.asyncio
async def test_expired_or_missing_selection_ignores_numbers(page_client, monkeypatch):
    c = page_client
    await c.handler(c.bot, c.event("2"))
    c.api.assert_not_awaited()
    c.manager.init.assert_not_awaited()
    monkeypatch.setattr(c.selections, "monotonic", lambda: 100)
    await c.handler(c.bot, c.event(c.video.bvid))
    monkeypatch.setattr(c.selections, "monotonic", lambda: 400)
    c.api.reset_mock()
    await c.handler(c.bot, c.event("2"))
    c.api.assert_not_awaited()
    c.download.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_video_replaces_pending_even_when_detail_fails(page_client):
    c = page_client
    await c.handler(c.bot, c.event(c.video.bvid))
    replacement = VideoInfo.from_api_data(c.video.to_dict())
    replacement.bvid = "BV1GJ411x7h7"
    replacement.pages = c.video.pages
    c.manager.get_video_detail.return_value = replacement
    await c.handler(c.bot, c.event(replacement.bvid))
    await c.handler(c.bot, c.event("2"))
    assert c.download.await_args.kwargs["bvid"] == replacement.bvid

    await c.handler(c.bot, c.event(replacement.bvid))
    c.manager.get_video_detail.return_value = None
    await c.handler(c.bot, c.event(c.video.bvid))
    c.api.reset_mock()
    await c.handler(c.bot, c.event("2"))
    c.api.assert_not_awaited()


@pytest.mark.asyncio
async def test_numeric_choice_rechecks_video_policy(page_client):
    c = page_client
    await c.handler(c.bot, c.event(c.video.bvid))
    for policies in (
        c.snapshot.link_parser_group_policies,
        c.snapshot.link_parser_user_policies,
    ):
        for key, policy in policies.items():
            policies[key] = replace(policy, video_enabled=False)
    c.api.reset_mock()
    await c.handler(c.bot, c.event("2"))
    c.api.assert_not_awaited()
    c.download.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("page", [1, 2, 0, 4])
async def test_explicit_page_skips_menu_or_reports_range(page_client, page):
    c = page_client
    await c.handler(
        c.bot, c.event(f"https://www.bilibili.com/video/{c.video.bvid}?p={page}")
    )
    caption = c.api.await_args.kwargs["message"].extract_plain_text()
    if page in {1, 2}:
        assert c.download.await_args.kwargs["cid"] == page * 100
        assert f"P{page} " in caption and f"?p={page}" in caption
    else:
        c.download.assert_not_awaited()
        assert "1～3" in caption
        await c.handler(c.bot, c.event("2"))
        assert c.download.await_args.kwargs["cid"] == 200


@pytest.mark.asyncio
async def test_failed_menu_does_not_enable_numeric_choice(page_client):
    c = page_client
    c.api.side_effect = RuntimeError("send failed")
    await c.handler(c.bot, c.event(c.video.bvid))
    c.api.reset_mock()
    await c.handler(c.bot, c.event("2"))
    c.api.assert_not_awaited()
    c.download.assert_not_awaited()


@pytest.mark.asyncio
async def test_simultaneous_numeric_choices_download_once(page_client):
    c = page_client
    await c.handler(c.bot, c.event(c.video.bvid))
    await asyncio.gather(c.handler(c.bot, c.event("2")), c.handler(c.bot, c.event("2")))
    c.download.assert_awaited_once()


@pytest.mark.asyncio
async def test_another_user_and_non_numeric_message_keep_selection(page_client):
    c = page_client
    await c.handler(c.bot, c.event(c.video.bvid))
    other = c.event("2")
    if isinstance(other, (GroupMessageEvent, PrivateMessageEvent)):
        other.user_id = 789
    elif isinstance(other, GroupAtMessageCreateEvent):
        other.author.member_openid = "other"
    else:
        other.author.user_openid = "other"
    c.api.reset_mock()
    await c.handler(c.bot, other)
    await c.handler(c.bot, c.event("P2"))
    c.api.assert_not_awaited()
    c.download.assert_not_awaited()
    await c.handler(c.bot, c.event("2"))
    assert c.download.await_args.kwargs["cid"] == 200


@pytest.mark.asyncio
async def test_single_page_link_clears_previous_menu(page_client):
    c = page_client
    await c.handler(c.bot, c.event(c.video.bvid))
    c.video.pages = c.video.pages[:1]
    await c.handler(c.bot, c.event(c.video.bvid))
    c.download.assert_awaited_once()
    assert c.download.await_args.kwargs["cid"] == 100
    c.api.reset_mock()
    await c.handler(c.bot, c.event("1"))
    c.api.assert_not_awaited()


def test_page_selection_is_scoped_and_bounded(page_client, monkeypatch):
    c = page_client
    key = c.plugin.selection_key(c.bot, c.event(""))
    c.plugin.remember_video(key, c.video)
    assert c.plugin.pending_video(key) is c.video
    for index, value in enumerate(
        ("other-adapter", "other-bot", "other-group", "other-user")
    ):
        other = list(key)
        other[index] = value
        assert c.plugin.pending_video(tuple(other)) is None
    other = list(key)
    other[2] = "group" if key[2] is None else None
    assert c.plugin.pending_video(tuple(other)) is None
    monkeypatch.setattr(c.selections, "_MAX_PENDING", 2)
    c.plugin.remember_video(("a", "b", None, "1"), c.video)
    c.plugin.remember_video(("a", "b", None, "2"), c.video)
    assert c.plugin.pending_video(key) is None
