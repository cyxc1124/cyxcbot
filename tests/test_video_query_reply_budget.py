"""Latest-video results share the native QQ event's limited reply budget."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.event import GroupAtMessageCreateEvent

from shared.adapter import outbound
from shared.adapter.official_runtime import _bot_info
from shared.config.command_aliases import normalize_command_aliases
from shared.config.types import AppConfigSnapshot
from utils.bilibili_api import VideoInfo


def _load_plugin():
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(sqlalchemy_database_url="sqlite+aiosqlite:///:memory:")
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    name = "video_reply_budget_test"
    if name not in sys.modules:
        path = Path(__file__).resolve().parents[1] / "plugins" / "video_monitor"
        spec = importlib.util.spec_from_file_location(
            name, path / "__init__.py", submodule_search_locations=[str(path)]
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _video(uid: int, *, cover=True, title=None):
    return VideoInfo(
        aid=uid,
        bvid=f"BV{uid}",
        title=title or f"视频标题 {uid}",
        description="",
        cover=f"https://example.com/{uid}.jpg" if cover else "",
        duration=12,
        pub_date=1710000000,
        author_uid=uid,
        author_name=f"UP {uid}",
    )


def _official_event():
    return GroupAtMessageCreateEvent.model_validate(
        {
            "id": "latest-video-query",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": "/最新视频",
            "group_id": "video-group",
            "group_openid": "video-group",
            "author": {
                "id": "video-user",
                "member_openid": "video-user",
                "member_role": "member",
                "bot": False,
            },
        }
    )


@pytest.fixture
def pipeline(monkeypatch):
    plugin = _load_plugin()
    snapshot = AppConfigSnapshot(command_aliases=normalize_command_aliases({}))
    service = SimpleNamespace(get_snapshot=lambda: snapshot)
    monkeypatch.setattr(plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    monkeypatch.setattr(
        outbound, "_materialize_media", AsyncMock(return_value=b"cover")
    )
    bot = QQBot(MagicMock(), "test-app", _bot_info("test-app", "test-secret", False))
    api = AsyncMock()
    monkeypatch.setattr(bot, "send_to_group", api)

    def set_results(results, group_id="video-group"):
        snapshot.dynamic_monitor_mapping = {str(uid): [group_id] for uid in results}
        monkeypatch.setattr(
            plugin,
            "get_cached_config",
            lambda: SimpleNamespace(
                bilibili_cookie="",
                get_uids_by_group_id=lambda group: (
                    list(results) if group == group_id else []
                ),
            ),
        )

        async def fetch(uid, **kwargs):
            result = results[str(uid)]
            if isinstance(result, BaseException):
                raise result
            return result

        manager = SimpleNamespace(
            init=AsyncMock(), get_user_videos=AsyncMock(side_effect=fetch)
        )
        monkeypatch.setattr("utils.bilibili_api.video_api_manager", manager)
        return manager

    return plugin, bot, api, set_results


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("cover", [True, False])
async def test_all_latest_videos_keep_title_and_url(pipeline, count, cover):
    plugin, bot, api, set_results = pipeline
    results = {str(uid): [_video(uid, cover=cover)] for uid in range(1, count + 1)}
    set_results(results)
    event = _official_event()
    await plugin.handle_video_commands(bot, event)
    calls = api.await_args_list
    assert len(calls) == 1 + (count if cover else 0)
    caption = calls[0].kwargs["message"].extract_plain_text()
    for uid in range(1, count + 1):
        assert f"UP {uid} 最新投稿" in caption
        assert f"视频标题 {uid}" in caption
        assert _video(uid).get_video_url() in caption
    assert calls[0].kwargs["message"][0].type == "text"
    assert all(call.kwargs["msg_id"] == event.id for call in calls)
    assert [call.kwargs["msg_seq"] for call in calls] == list(range(1, len(calls) + 1))


@pytest.mark.asyncio
@pytest.mark.parametrize("remaining", [1, 2])
async def test_previous_native_replies_leave_text_priority(pipeline, remaining):
    plugin, bot, api, set_results = pipeline
    set_results({str(uid): [_video(uid)] for uid in range(1, 4)})
    event = _official_event()
    event._reply_seq = 5 - remaining
    await plugin.handle_video_commands(bot, event)
    calls = api.await_args_list
    assert len(calls) == remaining
    assert [call.kwargs["msg_seq"] for call in calls] == list(range(6 - remaining, 6))
    caption = calls[0].kwargs["message"].extract_plain_text()
    assert all(_video(uid).get_video_url() in caption for uid in range(1, 4))
    assert outbound.official_reply_remaining(event) == 0


@pytest.mark.asyncio
async def test_failed_and_empty_uids_share_the_summary(pipeline):
    plugin, bot, api, set_results = pipeline
    set_results({"1": [_video(1)], "2": RuntimeError("query failed"), "3": []})
    event = _official_event()
    event._reply_seq = 4
    await plugin.handle_video_commands(bot, event)
    api.assert_awaited_once()
    caption = api.await_args.kwargs["message"].extract_plain_text()
    assert _video(1).get_video_url() in caption
    assert "UP主 2 视频查询失败，请稍后重试" in caption
    assert "无法获取UP主 3 的视频，请检查UID是否正确" in caption


@pytest.mark.asyncio
async def test_exhausted_budget_skips_query_and_send(pipeline):
    plugin, bot, api, set_results = pipeline
    manager = set_results({"1": [_video(1)]})
    event = _official_event()
    event._reply_seq = 5
    await plugin.handle_video_commands(bot, event)
    manager.init.assert_not_awaited()
    manager.get_user_videos.assert_not_awaited()
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_cover_failure_cannot_hide_results(pipeline):
    plugin, bot, api, set_results = pipeline
    set_results({"1": [_video(1)], "2": [_video(2)]})

    async def send(**kwargs):
        if kwargs["message"][0].type == "file_image":
            raise RuntimeError("cover rejected")

    api.side_effect = send
    await plugin.handle_video_commands(bot, _official_event())
    assert api.await_count == 3
    caption = api.await_args_list[0].kwargs["message"].extract_plain_text()
    assert _video(1).get_video_url() in caption
    assert _video(2).get_video_url() in caption
    assert all(
        call.kwargs["message"][0].type == "file_image"
        for call in api.await_args_list[1:]
    )


@pytest.mark.asyncio
async def test_long_titles_batch_without_cutting_video_links(pipeline):
    plugin, bot, api, set_results = pipeline
    set_results({str(uid): [_video(uid, title="长" * 2100)] for uid in range(1, 4)})
    await plugin.handle_video_commands(bot, _official_event())
    texts = [
        call.kwargs["message"].extract_plain_text()
        for call in api.await_args_list
        if call.kwargs["message"][0].type == "text"
    ]
    assert len(texts) == 3
    assert all(len(text) <= 2000 for text in texts)
    assert all(_video(uid).get_video_url() in texts[uid - 1] for uid in range(1, 4))
    assert api.await_count == 5


@pytest.mark.asyncio
async def test_text_over_budget_explains_omitted_results(pipeline):
    plugin, bot, api, set_results = pipeline
    set_results({str(uid): [_video(uid, title="长" * 2100)] for uid in range(1, 7)})
    await plugin.handle_video_commands(bot, _official_event())
    assert api.await_count == 5
    captions = [
        call.kwargs["message"].extract_plain_text() for call in api.await_args_list
    ]
    assert all(len(caption) <= 2000 for caption in captions)
    assert "部分 UP 主结果未展示" in captions[-1]
    assert _video(5).get_video_url() in captions[-1]


@pytest.mark.asyncio
async def test_onebot_keeps_individual_video_and_error_messages(pipeline):
    plugin, _, _, set_results = pipeline
    set_results({"1": [_video(1)], "2": [_video(2, cover=False)], "3": []}, "1001")
    event = SimpleNamespace(
        group_id=1001, user_id=2001, get_plaintext=lambda: "/最新视频"
    )
    bot = SimpleNamespace(send_group_msg=AsyncMock(), send=AsyncMock())
    await plugin.handle_video_commands(bot, event)
    assert bot.send_group_msg.await_count == 2
    first = bot.send_group_msg.await_args_list[0].kwargs["message"]
    second = bot.send_group_msg.await_args_list[1].kwargs["message"]
    assert first[1].type == "image"
    assert _video(1).get_video_url() in first.extract_plain_text()
    assert all(segment.type == "text" for segment in second)
    assert _video(2).get_video_url() in second.extract_plain_text()
    bot.send.assert_awaited_once_with(event, "无法获取UP主 3 的视频，请检查UID是否正确")
