"""Official QQ Douyin pipeline: native events, budget, and local-media cleanup."""

import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupAtMessageCreateEvent
from PIL import Image

from shared.adapter import outbound
from shared.adapter.official_runtime import _bot_info
from shared.adapter.qq_errors import LoggedQQApiError
from shared.config.douyin_link_parser_policy import (
    DouyinLinkParserGroupPolicyRecord,
    DouyinLinkParserUserPolicyRecord,
)
from shared.config.message_templates import DouyinLinkMessageTemplates
from shared.config.types import AppConfigSnapshot
from tests.test_config_service_load_perf import _ensure_real_db_modules
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


def _event(scope):
    cls = GroupAtMessageCreateEvent if scope == "group" else C2CMessageCreateEvent
    return cls.model_validate(
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


@pytest.fixture
def native_plugin(monkeypatch):
    import nonebot

    _ensure_real_db_modules()
    matcher = SimpleNamespace(handle=lambda: lambda fn: fn)
    monkeypatch.setattr(nonebot, "on_message", lambda **_: matcher)
    monkeypatch.setattr(
        nonebot, "get_driver", lambda: SimpleNamespace(on_startup=lambda fn: fn)
    )
    name = "douyin_native_handler_test"
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)]
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    yield module
    for key in list(sys.modules):
        if key.startswith(f"{name}."):
            sys.modules.pop(key)


@pytest.fixture
def message_guards(monkeypatch, native_plugin):
    import nonebot.message

    monkeypatch.setattr(nonebot.message, "event_preprocessor", lambda fn: fn)
    guards = {}
    for scope in ("group", "private"):
        spec = importlib.util.spec_from_file_location(
            f"douyin_test_{scope}_guard",
            ROOT / "plugins" / f"{scope}_guard" / "__init__.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        monkeypatch.setattr(module, "remember_official_session", AsyncMock())
        guards[scope] = module
    return guards


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize(
    "kind", ["video", "album", "live", "large", "many_live", "mixed"]
)
@pytest.mark.parametrize("reject", [False, True])
async def test_native_douyin_reply_and_cleanup(
    scope, kind, reject, tmp_path, monkeypatch, native_plugin, message_guards
):
    event = _event(scope)
    assert "douyin.com/video/200" in native_plugin.collect_message_text(event)
    count = (
        26
        if kind == "large"
        else 6
        if kind == "mixed"
        else 8
        if kind == "many_live"
        else 2
        if kind == "live"
        else 1
    )
    items, paths = [], []
    for i in range(count):
        video = (
            kind in {"video", "many_live"}
            or kind == "live"
            and i == 1
            or kind == "mixed"
            and i < 4
        )
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
    snapshot = AppConfigSnapshot(
        message_enabled_group_ids=["g-openid"],
        message_enabled_user_ids=["u-openid"],
        douyin_link_parser_group_policies={
            "g-openid": DouyinLinkParserGroupPolicyRecord("g-openid", enabled=True)
        },
        douyin_link_parser_user_policies={
            "u-openid": DouyinLinkParserUserPolicyRecord("u-openid", enabled=True)
        },
    )
    guard = message_guards["group" if scope == "group" else "private"]
    monkeypatch.setattr(
        guard,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: snapshot),
    )
    monkeypatch.setattr(
        native_plugin,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: snapshot),
    )
    monkeypatch.setattr(
        native_plugin,
        "get_config",
        lambda: native_plugin.Config(
            douyin_cookie="", message_templates=DouyinLinkMessageTemplates()
        ),
    )
    monkeypatch.setattr(native_plugin, "logger", logger)
    monkeypatch.setattr(native_plugin, "ensure_shared_media_dir", lambda _: tmp_path)
    download = AsyncMock(return_value=result)
    monkeypatch.setattr(native_plugin, "resolve_and_download", download)
    handler = (
        native_plugin.handle_group_douyin_link
        if scope == "group"
        else native_plugin.handle_private_douyin_link
    )
    await (
        guard.block_disabled_group_messages(event)
        if scope == "group"
        else guard.block_disabled_private_messages(event)
    )
    await handler(bot, event)
    download.assert_awaited_once_with(event.content, "", tmp_dir=tmp_path)
    expected = (
        1
        if reject
        else (5 if scope == "group" else 4)
        if kind in {"many_live", "mixed"}
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
        if kind in {"large", "mixed"}:
            assert ("26 张静态图片" if kind == "large" else "2 张静态图片") in caption
            segment = api.await_args_list[0].kwargs["message"][0]
            assert segment.type == "file_image"
            from io import BytesIO

            preview = Image.open(BytesIO(segment.data["content"]))
            assert preview.size == ((1280, 2240) if kind == "large" else (640, 320))
        if kind == "mixed":
            assert ("另有 1 项媒体" if scope == "group" else "另有 2 项媒体") in caption
            sent_videos = [
                call.kwargs["message"][0].data["file_name"]
                for call in api.await_args_list[1:-1]
            ]
            assert sent_videos == [
                path.name for path in paths[: (3 if scope == "group" else 2)]
            ]
        if kind == "many_live":
            assert ("另有 4 项媒体" if scope == "group" else "另有 5 项媒体") in caption
    assert not any(path.exists() for path in paths)
    assert not list(tmp_path.glob("douyin_preview_*.jpg"))
    logger.error.assert_not_called()
    logger.opt.return_value.error.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize("disabled", ["master", "leaf"])
async def test_native_handler_requires_master_and_leaf(
    scope, disabled, native_plugin, message_guards, monkeypatch
):
    from nonebot.exception import IgnoredException

    snapshot = AppConfigSnapshot(
        message_enabled_group_ids=[] if disabled == "master" else ["g-openid"],
        message_enabled_user_ids=[] if disabled == "master" else ["u-openid"],
        douyin_link_parser_group_policies={
            "g-openid": DouyinLinkParserGroupPolicyRecord(
                "g-openid", enabled=disabled != "leaf"
            )
        },
        douyin_link_parser_user_policies={
            "u-openid": DouyinLinkParserUserPolicyRecord(
                "u-openid", enabled=disabled != "leaf"
            )
        },
    )
    service = SimpleNamespace(get_snapshot=lambda: snapshot)
    guard = message_guards["group" if scope == "group" else "private"]
    monkeypatch.setattr(guard, "get_config_service", lambda: service)
    monkeypatch.setattr(native_plugin, "get_config_service", lambda: service)
    monkeypatch.setattr(native_plugin, "get_config", native_plugin.Config)
    download = AsyncMock()
    monkeypatch.setattr(native_plugin, "resolve_and_download", download)
    event = _event(scope)

    async def dispatch():
        if scope == "group":
            await guard.block_disabled_group_messages(event)
            await native_plugin.handle_group_douyin_link(SimpleNamespace(), event)
        else:
            await guard.block_disabled_private_messages(event)
            await native_plugin.handle_private_douyin_link(SimpleNamespace(), event)

    if disabled == "master":
        with pytest.raises(IgnoredException):
            await dispatch()
    else:
        await dispatch()
    download.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
@pytest.mark.parametrize("stage", ["render", "send"])
async def test_cancelling_native_handler_cleans_sources_and_preview(
    scope, stage, native_plugin, tmp_path, monkeypatch
):
    import threading

    paths = [tmp_path / f"{i}.jpg" for i in range(6)]
    for path in paths:
        Image.new("RGB", (60, 80)).save(path)
    result = DouyinVideoResult(
        aweme_id="200",
        title="caption",
        author="Author",
        share_url="https://www.douyin.com/note/200",
        file_path=paths[0],
        detail={},
        content_type="album",
        items=[DouyinMediaItem(kind="image", file_path=path) for path in paths],
    )
    snapshot = AppConfigSnapshot(
        douyin_link_parser_group_policies={
            "g-openid": DouyinLinkParserGroupPolicyRecord("g-openid", enabled=True)
        },
        douyin_link_parser_user_policies={
            "u-openid": DouyinLinkParserUserPolicyRecord("u-openid", enabled=True)
        },
    )
    monkeypatch.setattr(
        native_plugin,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: snapshot),
    )
    monkeypatch.setattr(native_plugin, "get_config", native_plugin.Config)
    monkeypatch.setattr(native_plugin, "ensure_shared_media_dir", lambda _: tmp_path)
    monkeypatch.setattr(
        native_plugin, "resolve_and_download", AsyncMock(return_value=result)
    )
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    bot = QQBot(MagicMock(), "app", _bot_info("app", "secret", False))
    started, release = threading.Event(), threading.Event()
    if stage == "render":
        official = sys.modules[f"{native_plugin.__name__}.official_reply"]
        original = official._album_preview

        def render(*args):
            started.set()
            release.wait(5)
            return original(*args)

        monkeypatch.setattr(official, "_album_preview", render)
        api = AsyncMock()
    else:

        async def send(**kwargs):
            started.set()
            await asyncio.Event().wait()

        api = AsyncMock(side_effect=send)
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", api
    )
    handler = (
        native_plugin.handle_group_douyin_link
        if scope == "group"
        else native_plugin.handle_private_douyin_link
    )
    task = asyncio.create_task(handler(bot, _event(scope)))
    assert await asyncio.to_thread(started.wait, 5)
    for _ in range(2):
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not any(path.exists() for path in paths)
    assert not list(tmp_path.glob("douyin_preview_*.jpg"))


@pytest.mark.asyncio
async def test_single_remaining_reply_does_not_claim_unsent_preview(
    tmp_path, monkeypatch
):
    from nonebot.adapters.onebot.v11 import Message, MessageSegment

    module = _load("official_reply")
    render = MagicMock()
    monkeypatch.setattr(module, "_album_preview", render)
    message = Message(
        [
            MessageSegment.image(tmp_path / "1.jpg"),
            MessageSegment.image(tmp_path / "2.jpg"),
            MessageSegment.text("caption"),
        ]
    )
    reply, generated = await module.prepare_official_reply(message, 1, tmp_path)
    render.assert_not_called()
    assert generated == []
    assert len(reply) == 1 and reply[0].type == "text"
    assert "2 项媒体" in reply.extract_plain_text()
    assert "已合成预览" not in reply.extract_plain_text()


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
