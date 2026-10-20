"""Quoted dynamic extraction through the normal command routing and handlers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.adapters.onebot.v11.bot import _check_reply
from test_live_monitor_command_handlers import _command_snapshot

from shared.config.command_aliases import normalize_command_aliases

DYNAMIC_ID = "1234567890123456789"
DYNAMIC_URL = f"https://t.bilibili.com/{DYNAMIC_ID}"


def _event(text, scope="group", *, quoted=DYNAMIC_URL, sender_id=999):
    message = Message(text)
    event_type = GroupMessageEvent if scope == "group" else PrivateMessageEvent
    return event_type(
        time=0,
        self_id=999,
        post_type="message",
        sub_type="normal" if scope == "group" else "friend",
        message_type=scope,
        message_id=2,
        user_id=123,
        message=message,
        original_message=message.copy(),
        raw_message=str(message),
        font=0,
        sender={"user_id": 123},
        reply=(
            {
                "time": 0,
                "message_type": scope,
                "message_id": 1,
                "real_id": 1,
                "sender": {"user_id": sender_id},
                "message": Message(quoted),
            }
            if quoted is not None
            else None
        ),
        **({"group_id": 456} if scope == "group" else {}),
    )


@pytest.fixture
def extraction(monkeypatch):
    from plugins.dynamic_monitor import dynamic_extract as extract

    snap = _command_snapshot(normalize_command_aliases({}))
    snap.dynamic_subscription_mapping = {"42": ["456"]}
    snap.dynamic_subscription_user_mapping = {"42": ["123"]}
    service = SimpleNamespace(get_snapshot=lambda: snap)
    monkeypatch.setattr(extract, "get_config_service", lambda: service)
    monkeypatch.setattr("shared.config.service.get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    monkeypatch.setattr(
        extract.Config,
        "from_service",
        lambda: SimpleNamespace(
            bilibili_cookie="", message_templates=snap.dynamic_message_templates
        ),
    )
    fetch = AsyncMock(return_value=["https://example.com/1.jpg"])
    send = AsyncMock()
    monkeypatch.setattr(extract, "_fetch_dynamic_images", fetch)
    monkeypatch.setattr(extract, "_send_reply", send)
    bot = MagicMock(spec=Bot)
    bot.self_id = "999"
    bot.config.superusers = set()
    return SimpleNamespace(module=extract, snap=snap, bot=bot, fetch=fetch, send=send)


@pytest.mark.parametrize(
    "scope,command,quoted",
    [
        ("group", "/提取", f"测试UP 发布了动态\n{DYNAMIC_URL}"),
        ("private", "#获取", f"https://www.bilibili.com/opus/{DYNAMIC_ID}?from=qq"),
        ("group", "/提取", f"{DYNAMIC_URL}\n{DYNAMIC_URL}"),
    ],
)
async def test_extract_quoted_dynamic(extraction, scope, command, quoted):
    event = _event(command, scope, quoted=quoted)
    handler = (
        extraction.module.handle_group_dynamic_extract
        if scope == "group"
        else extraction.module.handle_private_dynamic_extract
    )
    await handler(extraction.bot, event)
    extraction.fetch.assert_awaited_once_with(DYNAMIC_ID, None)
    reply = extraction.send.await_args.args[2]
    assert DYNAMIC_ID in reply.extract_plain_text()
    assert len(reply["image"]) == 1


@pytest.mark.parametrize(
    "quoted,sender_id",
    [
        (None, 999),
        (DYNAMIC_URL, 123),
        ("[引用消息]", 999),
        (DYNAMIC_ID, 999),
        (Message(MessageSegment.image("https://example.com/card.png")), 999),
        (f"{DYNAMIC_URL}\nhttps://t.bilibili.com/9876543210987654321", 999),
    ],
)
async def test_unusable_quote_requests_explicit_id(extraction, quoted, sender_id):
    event = _event("/提取", quoted=quoted, sender_id=sender_id)
    await extraction.module._handle_extract(extraction.bot, event)
    extraction.fetch.assert_not_awaited()
    assert "填写动态ID" in extraction.send.await_args.args[2]


@pytest.mark.parametrize("scope", ["group", "private"])
@pytest.mark.parametrize("disabled", [False, True], ids=["unsubscribed", "disabled"])
async def test_quote_respects_subscription_and_command_switch(
    extraction, scope, disabled
):
    if disabled:
        extraction.snap.command_aliases["dynamic_extract"].enabled = False
    else:
        extraction.snap.dynamic_subscription_mapping = {}
        extraction.snap.dynamic_subscription_user_mapping = {}
    await extraction.module._handle_extract(extraction.bot, _event("/提取", scope))
    extraction.fetch.assert_not_awaited()
    extraction.send.assert_not_awaited()


@pytest.mark.parametrize("command", ["提取", "/提取无效参数", "/提取123"])
async def test_quote_does_not_override_invalid_command(extraction, command):
    await extraction.module._handle_extract(extraction.bot, _event(command))
    extraction.fetch.assert_not_awaited()
    extraction.send.assert_not_awaited()


async def test_explicit_id_takes_precedence_over_quote(extraction):
    await extraction.module._handle_extract(
        extraction.bot,
        _event("/提取9876543210987654321", sender_id=123),
    )
    extraction.fetch.assert_awaited_once_with("9876543210987654321", None)


async def test_quote_supports_custom_trigger_and_prefix(extraction):
    extraction.snap.command_aliases["dynamic_extract"].triggers = ["采图"]
    extraction.snap.command_extra_prefixes = ["$"]
    await extraction.module._handle_extract(extraction.bot, _event("$采图"))
    extraction.fetch.assert_awaited_once_with(DYNAMIC_ID, None)


async def test_onebot_reply_is_resolved_before_extraction(extraction):
    event = _event(MessageSegment.reply(1) + MessageSegment.text("/提取"), quoted=None)
    extraction.bot.get_msg = AsyncMock(
        return_value=_event("", quoted=DYNAMIC_URL).reply.model_dump()
    )
    await _check_reply(extraction.bot, event)
    assert event.to_me
    assert not event.message["reply"]
    await extraction.module.handle_group_dynamic_extract(extraction.bot, event)
    extraction.bot.get_msg.assert_awaited_once_with(message_id=1)
    extraction.fetch.assert_awaited_once_with(DYNAMIC_ID, None)
