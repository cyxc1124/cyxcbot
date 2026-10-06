"""Official QQ adapter routing, inbound helpers, and outbound conversion."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq import Message as QQMessage
from nonebot.adapters.qq.event import (
    C2CMessageCreateEvent,
    FriendAddEvent,
    FriendDelEvent,
    GroupAtMessageCreateEvent,
)

from shared.adapter import outbound, sessions
from shared.adapter.ids import is_numeric_qq_id
from shared.adapter.inbound import (
    group_id_of,
    is_group_event,
    is_official_c2c_event,
    is_official_group_event,
    is_private_event,
    is_tome,
    user_id_of,
)
from shared.adapter.official_runtime import _bot_info
from shared.adapter.outbound import (
    convert_onebot_message,
    send_group,
    send_user,
    strip_urls,
)


def _official_event(scope: str):
    cls = GroupAtMessageCreateEvent if scope == "group" else C2CMessageCreateEvent
    return cls.model_validate(
        {
            "id": "test-message",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": "/status",
            "group_id": "test-group",
            "group_openid": "test-group",
            "author": {
                "id": "test-user",
                "user_openid": "test-user",
                "member_openid": "test-user",
                "bot": False,
                "member_role": "member",
            },
        }
    )


def test_numeric_id_routes_to_onebot() -> None:
    assert is_numeric_qq_id("1001")
    assert is_numeric_qq_id(" 120674547 ")
    assert not is_numeric_qq_id("C2C_OPENID")
    assert not is_numeric_qq_id("")


def test_inbound_official_group() -> None:
    event = SimpleNamespace(
        group_openid="g-openid",
        author=SimpleNamespace(member_openid="m-openid"),
        id="msg-1",
    )
    assert is_official_group_event(event)
    assert is_group_event(event)
    assert not is_private_event(event)
    assert group_id_of(event) == "g-openid"
    assert user_id_of(event) == "m-openid"
    assert is_tome(event)


def test_inbound_official_c2c() -> None:
    event = SimpleNamespace(
        author=SimpleNamespace(user_openid="u-openid"),
        id="msg-2",
    )
    assert is_official_c2c_event(event)
    assert is_private_event(event)
    assert not is_group_event(event)
    assert user_id_of(event) == "u-openid"
    assert is_tome(event)


def test_inbound_onebot_group_not_official() -> None:
    event = SimpleNamespace(group_id=1001, user_id=2002)
    assert is_group_event(event)
    assert not is_official_group_event(event)
    assert group_id_of(event) == "1001"
    assert user_id_of(event) == "2002"
    assert not is_tome(event)


def test_convert_drops_at_all_and_keeps_text() -> None:
    message = Message(
        [MessageSegment.at("all"), MessageSegment.text(" 新动态 https://b23.tv/x ")]
    )
    parts = convert_onebot_message(message)
    assert parts == [("text", " 新动态 https://b23.tv/x ")]


def test_strip_urls() -> None:
    assert "http" not in strip_urls("看 https://example.com/a 这里")
    assert strip_urls("无链接") == "无链接"


@pytest.mark.asyncio
async def test_send_group_numeric_uses_onebot() -> None:
    bot = MagicMock()
    bot.send_group_msg = AsyncMock()
    with patch("shared.adapter.outbound.iter_onebot_bots", return_value=[bot]):
        await send_group("1001", Message("hi"))
    bot.send_group_msg.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("send", [send_group, send_user])
async def test_proactive_official_send_is_rejected(send) -> None:
    with patch.object(outbound, "_send_official_parts", new=AsyncMock()) as send_parts:
        with pytest.raises(ValueError, match="不支持主动推送"):
            await send("official-openid", Message("hi"))
        send_parts.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_official_batches_share_native_reply_sequence_and_send_bytes(
    scope, monkeypatch
):
    event = _official_event(scope)
    bot = QQBot(MagicMock(), "test-app", _bot_info("test-app", "test-secret", False))
    send = AsyncMock()
    monkeypatch.setattr(
        bot, "send_to_group" if scope == "group" else "send_to_c2c", send
    )
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    await outbound.send_event_message(bot, event, Message("first batch"))
    # Matcher 的原生回复与共享适配层必须使用同一条序号链。
    await bot.send(event, QQMessage("native reply"))
    image = b"\x89PNG\r\n\x1a\n"
    await outbound.send_event_message(bot, event, Message(MessageSegment.image(image)))
    assert [call.kwargs["msg_seq"] for call in send.await_args_list] == [1, 2, 3]
    assert all(call.kwargs["msg_id"] == event.id for call in send.await_args_list)
    assert send.await_args.kwargs["message"][0].data["content"] == image


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", [None, "base64://!invalid!", "/missing/official-media.png"]
)
async def test_invalid_official_media_does_not_report_success(value):
    bot = QQBot(MagicMock(), "test-app", _bot_info("test-app", "test-secret", False))
    with patch.object(bot, "send", new=AsyncMock()) as send:
        with pytest.raises(ValueError):
            await outbound.send_event_message(
                bot,
                _official_event("group"),
                Message(MessageSegment("image", {"file": value})),
            )
        send.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_cache_survives_sibling_preprocessor_cancel() -> None:
    import anyio
    from nonebot.exception import IgnoredException

    finished = asyncio.Event()

    async def upsert(openid: str, kind: str, name: str = "") -> None:
        await asyncio.sleep(0.05)
        finished.set()

    event = SimpleNamespace(author=SimpleNamespace(user_openid="u-openid"), id="msg")

    async def ignore() -> None:
        await asyncio.sleep(0.01)
        raise IgnoredException("disabled")

    with patch.object(sessions, "upsert_session", upsert):
        with pytest.raises(BaseExceptionGroup):
            async with anyio.create_task_group() as tg:
                tg.start_soon(sessions.remember_official_session, event)
                tg.start_soon(ignore)
    assert finished.is_set()


@pytest.mark.asyncio
async def test_friend_notice_openid_updates_session_cache():
    data = {
        "id": "event-test",
        "timestamp": datetime.now(timezone.utc),
        "openid": "test-friend",
    }
    with (
        patch.object(sessions, "upsert_session", new=AsyncMock()) as add,
        patch.object(sessions, "delete_session", new=AsyncMock()) as delete,
    ):
        await sessions.cache_official_qq_session(FriendAddEvent.model_validate(data))
        await sessions.cache_official_qq_session(FriendDelEvent.model_validate(data))
    add.assert_awaited_once_with("test-friend", "c2c", "")
    delete.assert_awaited_once_with("test-friend")


@pytest.mark.asyncio
async def test_disconnect_cancels_adapter_forward_tasks() -> None:
    from shared.adapter.official_runtime import _disconnect

    started = asyncio.Event()

    async def sleeper() -> None:
        started.set()
        await asyncio.sleep(60)

    task = asyncio.create_task(sleeper())
    await started.wait()
    bot = SimpleNamespace(self_id="test-app")
    adapter = SimpleNamespace(tasks={task}, bot_disconnect=MagicMock())
    with patch("shared.adapter.bots.iter_official_bots", return_value=[bot]):
        await _disconnect(adapter)
    assert task.cancelled()
    assert adapter.tasks == set()
    adapter.bot_disconnect.assert_called_once_with(bot)


@pytest.mark.asyncio
async def test_apply_skips_webhook_when_already_applied() -> None:
    from shared.adapter import official_runtime as runtime

    snap = SimpleNamespace(
        official_qq_app_id="123456",
        official_qq_app_secret="secret",
        official_qq_is_sandbox=False,
        official_qq_use_websocket=False,
    )
    adapter = SimpleNamespace(
        qq_config=SimpleNamespace(qq_is_sandbox=False, qq_bots=[]),
        run_bot_websocket=AsyncMock(),
    )
    runtime._applied_key = ("123456", "secret", False, False)
    try:
        with (
            patch.object(runtime, "_get_adapter", return_value=adapter),
            patch("shared.adapter.bots.iter_official_bots", return_value=[]),
            patch.object(runtime, "_disconnect", new=AsyncMock()) as disconnect,
        ):
            await runtime.apply_official_runtime(snap)
        disconnect.assert_not_awaited()
        adapter.run_bot_websocket.assert_not_called()
    finally:
        runtime._applied_key = None


@pytest.mark.asyncio
async def test_webhook_credentials_verify_signed_event_and_clear(monkeypatch):
    from nonebot.adapters.qq import Adapter as QQAdapter
    from nonebot.adapters.qq.config import Config as QQConfig
    from nonebot.drivers import Request

    from shared.adapter import official_runtime as runtime

    monkeypatch.setattr(QQAdapter, "setup", lambda self: None)
    monkeypatch.setattr(
        "nonebot.adapters.qq.adapter.get_plugin_config", lambda _: QQConfig()
    )
    driver = SimpleNamespace(_bot_connect=MagicMock(), _bot_disconnect=MagicMock())
    adapter = QQAdapter(driver)
    monkeypatch.setattr(runtime, "_get_adapter", lambda: adapter)
    monkeypatch.setattr(runtime, "_applied_key", None)
    monkeypatch.setattr(
        "shared.adapter.bots.iter_official_bots", lambda: list(adapter.bots.values())
    )
    snap = SimpleNamespace(
        official_qq_app_id="test-app",
        official_qq_app_secret="test-secret",
        official_qq_is_sandbox=False,
        official_qq_use_websocket=False,
    )
    await runtime.apply_official_runtime(snap)
    info = adapter.qq_config.qq_bots[0]
    assert not info.use_websocket
    assert not adapter.tasks
    headers = {"X-Bot-Appid": info.id}
    challenge = json.dumps(
        {"op": 13, "d": {"plain_token": "challenge", "event_ts": "123"}}
    )
    response = await adapter._handle_http(
        Request("POST", "http://test/qq/webhook", headers=headers, content=challenge)
    )
    assert response.status_code == 200
    assert json.loads(response.content)["plain_token"] == "challenge"
    assert not adapter.bots  # 回调验证不等同于收到有效事件。

    payload = json.dumps(
        {
            "op": 0,
            "t": "C2C_MESSAGE_CREATE",
            "s": 1,
            "id": "event-test",
            "d": _official_event("c2c").model_dump(mode="json"),
        }
    )
    response = await adapter._handle_http(
        Request("POST", "http://test/qq/webhook", headers=headers, content=payload)
    )
    assert response.status_code == 403
    assert not adapter.bots
    key = adapter._get_ed25519_key(QQBot(adapter, info.id, info))
    headers.update(
        {
            "X-Signature-Timestamp": "123",
            "X-Signature-Ed25519": key.sign(b"123" + payload.encode()).hex(),
        }
    )
    with (
        patch.object(
            QQBot,
            "me",
            new=AsyncMock(return_value=SimpleNamespace(id="bot", username="test")),
        ),
        patch.object(adapter, "dispatch_event") as dispatch,
    ):
        response = await adapter._handle_http(
            Request("POST", "http://test/qq/webhook", headers=headers, content=payload)
        )
    assert response.status_code == 200
    assert info.id in adapter.bots
    dispatch.assert_called_once()
    snap.official_qq_app_secret = ""
    await runtime.apply_official_runtime(snap)
    assert not adapter.bots
    assert not adapter.qq_config.qq_bots
    response = await adapter._handle_http(
        Request("POST", "http://test/qq/webhook", headers=headers, content=payload)
    )
    assert response.status_code == 403
