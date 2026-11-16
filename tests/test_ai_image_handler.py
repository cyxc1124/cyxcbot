"""Quoted-image command routing, failure isolation, and concurrent request limits."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from ai_image_helpers import image_event
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.bot import _check_reply

import plugins.ai_image_detector as plugin
from plugins.ai_image_detector.c2pa_check import C2PAResult
from plugins.ai_image_detector.image import ImageDetectionError
from shared.config.ai_image import VisionProviderRecord
from shared.config.command_aliases import normalize_command_aliases
from shared.config.proxies import ProxyRecord
from shared.config.proxy import ProxyConfig
from shared.config.types import AppConfigSnapshot
from utils.vision_api import VisionAPIError, VisionImage, VisionVerdict

PROXY_RECORD = ProxyRecord(
    id="px", name="测试代理", scheme="http", host="proxy.test", port=7890
)
PROXY = PROXY_RECORD.to_config()
PREPARED = VisionImage("image/jpeg", "dmlzaW9uLWltYWdl")


@pytest.fixture(autouse=True)
def _fixed_command_start(monkeypatch):
    monkeypatch.setattr(nonebot.get_driver().config, "command_start", {"/"})


def _provider(name, **kwargs):
    return VisionProviderRecord(
        id=name, name=name, api_type="openai", model="vision-test", **kwargs
    )


@pytest.fixture
def detector(monkeypatch):
    fetch = AsyncMock(return_value=b"original-image")
    send = AsyncMock()
    local = MagicMock(return_value=C2PAResult("absent"))
    remote = AsyncMock(
        return_value={
            "c2pa": {"outcome": "not_detected", "validation_state": "not_present"},
            "synthid": {"outcome": "detected"},
        }
    )
    vision = AsyncMock(return_value=VisionVerdict("ai", 80, "test-only-reason"))
    monkeypatch.setattr(plugin, "download_image", fetch)
    monkeypatch.setattr(plugin, "image_media_type", lambda data: "image/png")
    monkeypatch.setattr(plugin, "inspect_c2pa", local)
    monkeypatch.setattr(plugin, "send_event_message", send)
    monkeypatch.setattr(plugin, "check_openai", remote)
    monkeypatch.setattr(plugin, "judge_image", vision)
    monkeypatch.setattr(plugin, "prepare_vision_image", lambda data: PREPARED)
    state = SimpleNamespace(
        snapshot=AppConfigSnapshot(
            command_aliases=normalize_command_aliases({}),
            ai_image_openai_api_key="test-only-key",
            proxies=(PROXY_RECORD,),
            ai_image_openai_proxy_id="px",
            ai_image_openai_proxy=PROXY,
        )
    )
    monkeypatch.setattr(
        plugin,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: state.snapshot),
    )
    monkeypatch.setattr(plugin, "_detection_lock", asyncio.Lock())
    bot = MagicMock(spec=Bot)
    bot.self_id = "999"
    bot.config = SimpleNamespace(superusers=set())
    bot.adapter = MagicMock()
    bot.adapter.get_name.return_value = "OneBot V11"

    def configure(**changes):
        state.snapshot = replace(state.snapshot, **changes)

    return SimpleNamespace(
        bot=bot,
        fetch=fetch,
        send=send,
        local=local,
        remote=remote,
        vision=vision,
        configure=configure,
    )


async def _detect(detector, url="https://gchat.qpic.cn/a", **kwargs):
    await plugin.handle_ai_image(
        detector.bot, image_event(quoted=MessageSegment.image(url), **kwargs)
    )
    return detector.send.await_args.args[2]


@pytest.mark.parametrize(
    "text", ["ai吗？", "AI吗?", "ai吗", " Ai吗？ ", "/ai吗？", "#AI吗"]
)
async def test_default_triggers_ignore_case_and_accept_prefixes(detector, text):
    assert await plugin.is_ai_image_command(detector.bot, image_event(text))


@pytest.mark.parametrize("text", ["这张是ai吗？", "ai吗？别的内容", "ai 吗"])
async def test_other_conversation_does_not_trigger(detector, text):
    assert not await plugin.is_ai_image_command(detector.bot, image_event(text))


@pytest.mark.parametrize(
    ("text", "quoted", "expected"),
    [
        ("你是ai吗？", None, False),
        ("ai吗", None, True),
        ("这张是AI吗？", MessageSegment.image("https://gchat.qpic.cn/a"), True),
    ],
)
async def test_mentions_match_loosely_only_when_quoting(
    detector, text, quoted, expected
):
    event = image_event(text, quoted=quoted)
    event.to_me = True
    assert await plugin.is_ai_image_command(detector.bot, event) is expected


@pytest.mark.parametrize("scope", ["official-group", "official-c2c"])
async def test_official_qq_messages_never_own_the_command(detector, scope):
    from test_live_monitor_command_handlers import _scoped_event

    from shared.config.command_aliases import command_aliases_for_event

    snapshot = AppConfigSnapshot(command_aliases=normalize_command_aliases({}))
    aliases = await command_aliases_for_event(
        snapshot, detector.bot, _scoped_event(scope, True)
    )
    assert not aliases["ai_image_detect"].enabled


async def test_custom_trigger_replaces_default_and_can_be_disabled(detector):
    detector.configure(
        command_aliases=normalize_command_aliases(
            {"ai_image_detect": {"enabled": True, "triggers": ["鉴图"]}}
        )
    )
    assert await plugin.is_ai_image_command(detector.bot, image_event("鉴图"))
    assert not await plugin.is_ai_image_command(detector.bot, image_event("ai吗？"))
    detector.configure(
        command_aliases=normalize_command_aliases(
            {"ai_image_detect": {"enabled": False, "triggers": ["鉴图"]}}
        )
    )
    assert not await plugin.is_ai_image_command(detector.bot, image_event("鉴图"))


@pytest.mark.parametrize("scope", ["group", "private"])
async def test_quote_detects_in_group_and_private_without_transcoding(detector, scope):
    event = image_event(
        scope=scope, quoted=MessageSegment.image("https://gchat.qpic.cn/original")
    )
    await plugin.handle_ai_image(detector.bot, event)
    detector.fetch.assert_awaited_once_with("https://gchat.qpic.cn/original")
    detector.remote.assert_awaited_once_with(
        b"original-image", "image/png", "test-only-key", proxy=PROXY
    )
    detector.vision.assert_not_awaited()
    reply = detector.send.await_args.args[2]
    assert reply[0] == MessageSegment.reply(event.reply.message_id)
    assert event.reply.message_id != event.message_id
    assert "检出水印" in reply.extract_plain_text()
    assert "视觉模型" not in reply.extract_plain_text()


@pytest.mark.parametrize(
    "quoted", [None, "文字", MessageSegment.image("a") + MessageSegment.image("b")]
)
async def test_missing_or_ambiguous_picture_does_not_download(detector, quoted):
    event = image_event(quoted=quoted)
    await plugin.handle_ai_image(detector.bot, event)
    detector.fetch.assert_not_awaited()
    detector.remote.assert_not_awaited()
    text = detector.send.await_args.args[2].extract_plain_text()
    assert "只包含一张图片" in text
    assert "「ai吗？」" in text
    target_id = event.reply.message_id if event.reply else event.message_id
    assert detector.send.await_args.args[2][0] == MessageSegment.reply(target_id)


async def test_onebot_resolves_quote_before_command_rule(detector):
    original = image_event(
        quoted=MessageSegment.image("https://gchat.qpic.cn/original")
    )
    event = image_event(MessageSegment.reply(1) + MessageSegment.text("ai吗？"))
    detector.bot.get_msg = AsyncMock(return_value=original.reply.model_dump())
    await _check_reply(detector.bot, event)
    assert await plugin.is_ai_image_command(detector.bot, event)
    await plugin.handle_ai_image(detector.bot, event)
    detector.fetch.assert_awaited_once()
    assert detector.send.await_args.args[2][0] == MessageSegment.reply(1)


async def test_no_api_key_keeps_local_result_and_skips_upload(detector):
    detector.configure(ai_image_openai_api_key="")
    text = (await _detect(detector)).extract_plain_text()
    detector.remote.assert_not_awaited()
    assert "尚未配置" in text
    assert "无法判断" in text


async def test_remote_failure_keeps_local_ai_declaration(detector):
    detector.local.return_value = C2PAResult("present", True, "Valid")
    detector.remote.side_effect = ImageDetectionError("请求受限")
    reply = await _detect(detector)
    text = reply.extract_plain_text()
    assert "含 AI 生成/编辑声明" in text
    assert "请求受限" in text
    assert "未检出水印" not in text
    assert reply[0] == MessageSegment.reply(1)


async def test_disabled_sources_are_neither_called_nor_reported(detector):
    detector.configure(
        ai_image_local_c2pa_enabled=False,
        ai_image_openai_c2pa_enabled=False,
        ai_image_openai_synthid_enabled=False,
        ai_image_vision_providers=(_provider("视觉"),),
    )
    text = (await _detect(detector)).extract_plain_text()
    detector.local.assert_not_called()
    detector.remote.assert_not_awaited()
    assert "C2PA" not in text and "SynthID" not in text
    assert "视觉：倾向 AI 生成（置信度 80%），test-only-reason" in text
    assert "结论：1/1 个视觉模型倾向 AI 生成，仅供参考" in text


async def test_single_openai_switch_still_uses_one_request_but_hides_other_signal(
    detector,
):
    detector.configure(ai_image_openai_synthid_enabled=False)
    text = (await _detect(detector)).extract_plain_text()
    detector.remote.assert_awaited_once()
    assert "OpenAI C2PA：未检出" in text
    assert "SynthID" not in text
    assert "检测到 AI 生成/编辑的来源证据" not in text


async def test_nothing_enabled_never_downloads(detector):
    detector.configure(
        ai_image_local_c2pa_enabled=False,
        ai_image_openai_c2pa_enabled=False,
        ai_image_openai_synthid_enabled=False,
        ai_image_vision_providers=(_provider("停用", enabled=False),),
    )
    text = (await _detect(detector)).extract_plain_text()
    detector.fetch.assert_not_awaited()
    assert "尚未启用任何图片检测方式" in text


async def test_vision_providers_run_with_their_own_proxy_and_isolate_failures(
    detector,
):
    direct = _provider("直连")
    proxied = _provider("代理", proxy_id="px")
    detector.configure(ai_image_vision_providers=(direct, proxied))

    async def vision(provider, image, *, proxy):
        # 所有供应商共用同一份编码结果。
        assert image is PREPARED
        # 各模型按自己选择的代理连接；未选择时直接连接。
        assert proxy == (PROXY if provider.proxy_id else ProxyConfig())
        if provider is direct:
            raise RuntimeError("sensitive upstream detail")
        return VisionVerdict("not_ai")

    detector.vision.side_effect = vision
    text = (await _detect(detector)).extract_plain_text()
    assert detector.vision.await_count == 2
    assert "直连：未完成，检测失败" in text
    assert "sensitive" not in text
    assert "代理：倾向非 AI 生成" in text
    # SynthID 检出属于来源证据，视觉模型意见不改变该结论。
    assert "检测到 AI 生成/编辑的来源证据" in text


async def test_upstream_error_detail_stays_out_of_group_replies(detector):
    detector.configure(ai_image_vision_providers=(_provider("视觉"),))
    detector.vision.side_effect = VisionAPIError(
        "API Key 无效，请管理员检查配置。", "upstream-only-detail"
    )
    text = (await _detect(detector)).extract_plain_text()
    assert "视觉：未完成，API Key 无效" in text
    assert "upstream-only-detail" not in text


async def test_unconvertible_image_only_fails_vision(detector, monkeypatch):
    def broken(data):
        raise VisionAPIError("图片无法转换为视觉模型可读取的格式。")

    monkeypatch.setattr(plugin, "prepare_vision_image", broken)
    detector.configure(ai_image_vision_providers=(_provider("视觉"),))
    text = (await _detect(detector)).extract_plain_text()
    detector.vision.assert_not_awaited()
    assert "视觉：未完成，图片无法转换" in text
    assert "SynthID（OpenAI）：检出水印" in text


async def test_unexpected_openai_error_does_not_hide_other_results(detector):
    detector.remote.side_effect = RuntimeError("sensitive")
    detector.configure(ai_image_vision_providers=(_provider("视觉"),))
    text = (await _detect(detector)).extract_plain_text()
    assert "OpenAI 检测失败" in text
    assert "sensitive" not in text
    assert "视觉：倾向 AI 生成" in text


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
    reply = await _detect(detector)
    assert not plugin._detection_lock.locked()
    assert "sensitive" not in str(reply)
    assert reply[0] == MessageSegment.reply(1)


async def test_get_image_url_fallback_never_reads_local_file(detector):
    event = image_event(quoted=Message(MessageSegment("image", {"file": "hash.image"})))
    detector.bot.get_image = AsyncMock(
        return_value={"file": "/private/file", "url": "https://gchat.qpic.cn/a"}
    )
    await plugin.handle_ai_image(detector.bot, event)
    detector.bot.get_image.assert_awaited_once_with(file="hash.image")
    detector.fetch.assert_awaited_once_with("https://gchat.qpic.cn/a")
