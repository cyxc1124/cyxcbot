"""Native QQ events through Bilibili policy, resolution, sending and cleanup."""

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
