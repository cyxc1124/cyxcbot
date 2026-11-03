"""Quoted-image command routing, failure isolation, and concurrent request limits."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ai_image_helpers import image_event
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.bot import _check_reply

import plugins.ai_image_detector as plugin
from plugins.ai_image_detector.c2pa_check import C2PAResult
from plugins.ai_image_detector.image import ImageDetectionError


@pytest.fixture
def detector(monkeypatch):
    fetch = AsyncMock(return_value=b"original-image")
    send = AsyncMock()
    remote = AsyncMock(
        return_value={
            "c2pa": {"outcome": "not_detected", "validation_state": "not_present"},
            "synthid": {"outcome": "detected"},
        }
    )
    monkeypatch.setattr(plugin, "download_image", fetch)
    monkeypatch.setattr(plugin, "image_media_type", lambda data: "image/png")
    monkeypatch.setattr(plugin, "inspect_c2pa", lambda data: C2PAResult("absent"))
    monkeypatch.setattr(plugin, "send_event_message", send)
    monkeypatch.setattr(plugin, "check_openai", remote)
    snapshot = SimpleNamespace(ai_image_openai_api_key="test-only-key")
    monkeypatch.setattr(
        plugin,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: snapshot),
    )
    monkeypatch.setattr(plugin, "_detection_lock", asyncio.Lock())
    bot = MagicMock(spec=Bot)
    bot.self_id = "999"
    return SimpleNamespace(
        bot=bot, fetch=fetch, send=send, remote=remote, snapshot=snapshot
    )


@pytest.mark.parametrize("text", ["ai吗？", "AI吗?", "ai吗", " Ai吗？ "])
def test_exact_command_accepts_case_and_question_marks(text):
    assert plugin.is_ai_image_command(image_event(text))


@pytest.mark.parametrize("text", ["这张是ai吗？", "/ai吗？", "ai吗？别的内容"])
def test_other_conversation_does_not_trigger(text):
    assert not plugin.is_ai_image_command(image_event(text))


@pytest.mark.parametrize("scope", ["group", "private"])
async def test_quote_detects_in_group_and_private_without_transcoding(detector, scope):
    event = image_event(
        scope=scope, quoted=MessageSegment.image("https://gchat.qpic.cn/original")
    )
    await plugin.handle_ai_image(detector.bot, event)
    detector.fetch.assert_awaited_once_with("https://gchat.qpic.cn/original")
    detector.remote.assert_awaited_once_with(
        b"original-image", "image/png", "test-only-key"
    )
    reply = detector.send.await_args.args[2]
    assert reply[0] == MessageSegment.reply(event.reply.message_id)
    assert event.reply.message_id != event.message_id
    assert "检出水印" in reply.extract_plain_text()


@pytest.mark.parametrize(
    "quoted", [None, "文字", MessageSegment.image("a") + MessageSegment.image("b")]
)
async def test_missing_or_ambiguous_picture_does_not_download(detector, quoted):
    event = image_event(quoted=quoted)
    await plugin.handle_ai_image(detector.bot, event)
    detector.fetch.assert_not_awaited()
    detector.remote.assert_not_awaited()
    assert "只包含一张图片" in detector.send.await_args.args[2].extract_plain_text()
    target_id = event.reply.message_id if event.reply else event.message_id
    assert detector.send.await_args.args[2][0] == MessageSegment.reply(target_id)


async def test_onebot_resolves_quote_before_command_rule(detector):
    original = image_event(
        quoted=MessageSegment.image("https://gchat.qpic.cn/original")
    )
    event = image_event(MessageSegment.reply(1) + MessageSegment.text("ai吗？"))
    detector.bot.get_msg = AsyncMock(return_value=original.reply.model_dump())
    await _check_reply(detector.bot, event)
    assert plugin.is_ai_image_command(event)
    await plugin.handle_ai_image(detector.bot, event)
    detector.fetch.assert_awaited_once()
    assert detector.send.await_args.args[2][0] == MessageSegment.reply(1)


async def test_no_api_key_keeps_local_result_and_skips_upload(detector):
    detector.snapshot.ai_image_openai_api_key = ""
    await plugin.handle_ai_image(
        detector.bot,
        image_event(quoted=MessageSegment.image("https://gchat.qpic.cn/a")),
    )
    detector.remote.assert_not_awaited()
    text = detector.send.await_args.args[2].extract_plain_text()
    assert "尚未配置" in text
    assert "无法判断" in text


async def test_remote_failure_keeps_local_ai_declaration(detector, monkeypatch):
    monkeypatch.setattr(
        plugin, "inspect_c2pa", lambda data: C2PAResult("present", True, "Valid")
    )
    detector.remote.side_effect = ImageDetectionError("请求受限")
    await plugin.handle_ai_image(
        detector.bot,
        image_event(quoted=MessageSegment.image("https://gchat.qpic.cn/a")),
    )
    text = detector.send.await_args.args[2].extract_plain_text()
    assert "含 AI 生成/编辑声明" in text
    assert "请求受限" in text
    assert "未检出水印" not in text
    assert detector.send.await_args.args[2][0] == MessageSegment.reply(1)


async def test_busy_request_never_starts_another_download(detector):
    async with plugin._detection_lock:
        await plugin.handle_ai_image(
            detector.bot,
            image_event(quoted=MessageSegment.image("https://gchat.qpic.cn/a")),
        )
    detector.fetch.assert_not_awaited()
    assert "稍后再试" in detector.send.await_args.args[2].extract_plain_text()
    assert detector.send.await_args.args[2][0] == MessageSegment.reply(1)


async def test_native_failure_releases_lock_and_returns_safe_message(detector):
    detector.fetch.side_effect = RuntimeError("sensitive download URL")
    await plugin.handle_ai_image(
        detector.bot,
        image_event(quoted=MessageSegment.image("https://gchat.qpic.cn/a")),
    )
    assert not plugin._detection_lock.locked()
    assert "sensitive" not in str(detector.send.await_args.args[2])
    assert detector.send.await_args.args[2][0] == MessageSegment.reply(1)


async def test_get_image_url_fallback_never_reads_local_file(detector):
    event = image_event(quoted=Message(MessageSegment("image", {"file": "hash.image"})))
    detector.bot.get_image = AsyncMock(
        return_value={"file": "/private/file", "url": "https://gchat.qpic.cn/a"}
    )
    await plugin.handle_ai_image(detector.bot, event)
    detector.bot.get_image.assert_awaited_once_with(file="hash.image")
    detector.fetch.assert_awaited_once_with("https://gchat.qpic.cn/a")
