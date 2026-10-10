"""Tests for monitor notification delivery results and retry behavior."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nonebot.adapters.onebot.v11.message import Message

from shared.notify.delivery import DeliveryResult, TargetDelivery, aggregate_by_target

ROOT = Path(__file__).resolve().parents[1]


def _delivery_failed() -> DeliveryResult:
    return DeliveryResult(targets=[TargetDelivery("group", "1001", False, "offline")])


def _delivery_succeeded() -> DeliveryResult:
    return DeliveryResult(targets=[TargetDelivery("group", "1001", True)])


PLUGINS_ROOT = ROOT / "plugins"
DYNAMIC_MONITOR_ROOT = PLUGINS_ROOT / "dynamic_monitor"
LIVE_MONITOR_ROOT = PLUGINS_ROOT / "live_monitor"


def _ensure_package(name: str, path: Path) -> types.ModuleType:
    if name in sys.modules:
        module = sys.modules[name]
        if not getattr(module, "__path__", None):
            module.__path__ = [str(path)]
        return module
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


def _load_module(qualified_name: str, plugin_root: Path, filename: str):
    path = plugin_root / filename
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(plugin_root)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dynamic_sender_module():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.dynamic_monitor", DYNAMIC_MONITOR_ROOT)
    return _load_module(
        "plugins.dynamic_monitor.sender",
        DYNAMIC_MONITOR_ROOT,
        "sender.py",
    )


@pytest.fixture
def live_sender_module():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", LIVE_MONITOR_ROOT)
    return _load_module(
        "plugins.live_monitor.sender",
        LIVE_MONITOR_ROOT,
        "sender.py",
    )


@pytest.fixture
def live_models_module():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", LIVE_MONITOR_ROOT)
    return _load_module(
        "plugins.live_monitor.models",
        LIVE_MONITOR_ROOT,
        "models.py",
    )


@pytest.fixture
def dynamic_monitor_module(monkeypatch):
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.dynamic_monitor", DYNAMIC_MONITOR_ROOT)
    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock()),
    )
    sys.modules.setdefault(
        "utils.screenshot",
        MagicMock(
            init_screenshot_service=AsyncMock(),
            close_screenshot_service=AsyncMock(),
            get_dynamic_screenshot=AsyncMock(),
        ),
    )
    _load_module(
        "plugins.dynamic_monitor.config",
        DYNAMIC_MONITOR_ROOT,
        "config.py",
    )
    _load_module(
        "plugins.dynamic_monitor.sender",
        DYNAMIC_MONITOR_ROOT,
        "sender.py",
    )
    module = _load_module(
        "plugins.dynamic_monitor.dynamic_monitor",
        DYNAMIC_MONITOR_ROOT,
        "dynamic_monitor.py",
    )
    monkeypatch.setattr(module.DynamicMonitorStateStore, "persist", AsyncMock())
    return module


@pytest.fixture
def live_monitor_module(monkeypatch):
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.live_monitor", LIVE_MONITOR_ROOT)
    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock()),
    )
    _load_module(
        "plugins.live_monitor.config",
        LIVE_MONITOR_ROOT,
        "config.py",
    )
    _load_module(
        "plugins.live_monitor.models",
        LIVE_MONITOR_ROOT,
        "models.py",
    )
    _load_module(
        "plugins.live_monitor.sender",
        LIVE_MONITOR_ROOT,
        "sender.py",
    )
    module = _load_module(
        "plugins.live_monitor.live_monitor",
        LIVE_MONITOR_ROOT,
        "live_monitor.py",
    )
    monkeypatch.setattr(module.LiveMonitorStateStore, "persist", AsyncMock())
    return module


@pytest.fixture
def x_monitor_module(dynamic_monitor_module):
    root = PLUGINS_ROOT / "x_monitor"
    _ensure_package("plugins.x_monitor", root)
    return _load_module("plugins.x_monitor.x_monitor", root, "x_monitor.py")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["dynamic", "x"])
async def test_official_monitor_targets_route_alongside_onebot(
    kind, dynamic_monitor_module, x_monitor_module
):
    cls = (
        dynamic_monitor_module.DynamicMonitor
        if kind == "dynamic"
        else x_monitor_module.XMonitor
    )
    monitor = object.__new__(cls)
    groups = ["official-group"]
    monitor.config = SimpleNamespace(
        **{
            f"{kind}_monitor_mapping": {"target": groups},
            f"{kind}_monitor_user_mapping": {"target": ["official-user"]},
            f"{kind}_at_all": {},
            "enable_screenshot": False,
        }
    )
    monitor.sender = SimpleNamespace(
        build_dynamic_message=MagicMock(return_value=Message("result")),
        build_tweet_message=MagicMock(return_value=Message("result")),
        plan_fingerprint=MagicMock(return_value="plan"),
        send_message=AsyncMock(return_value=_delivery_succeeded()),
    )
    monitor._pending_tweet_delivery = {
        "target": ("tweet", "", [("official-group", 0)], [])
    }
    monitor.last_tweet_ids = {}
    monitor._fetch_dynamic_screenshot = AsyncMock(return_value=None)
    monitor._resolve_author_name = AsyncMock(return_value="author")
    monitor.session = None
    monitor._persist_state = AsyncMock()
    item = SimpleNamespace(
        id="new-item",
        name="author",
        media_items=[],
        media_urls=[],
        get_type_description=lambda: "text",
    )
    send = (
        monitor._send_dynamic_notification
        if kind == "dynamic"
        else monitor._send_tweet_notification
    )
    assert await send("target", item)
    assert monitor.sender.send_message.await_args.args[1:3] == (
        ["official-group"],
        ["official-user"],
    )
    groups.append("1001")
    item.id = "next-item"
    assert await send("target", item)
    assert monitor.sender.send_message.await_args.args[1:3] == (
        ["official-group", "1001"],
        ["official-user"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("remove_all", [False, True])
async def test_x_mapping_reload_during_plan_persist_filters_old_targets(
    x_monitor_module, legacy, remove_all
):
    from utils.x_api.models import TweetItem

    monitor = object.__new__(x_monitor_module.XMonitor)
    monitor.config = SimpleNamespace(
        x_monitor_mapping={"author": ["removed-group", "kept-group"]},
        x_monitor_user_mapping={"author": ["removed-user", "kept-user"]},
        x_at_all={},
    )
    monitor.sender = SimpleNamespace(
        build_tweet_message=MagicMock(return_value=Message("caption")),
        plan_fingerprint=MagicMock(return_value="plan"),
        send_message=AsyncMock(return_value=_delivery_succeeded()),
    )
    monitor._pending_tweet_delivery = {}
    if legacy:
        monitor._pending_tweet_delivery["author"] = (
            "200",
            "plan",
            [("removed-group", 1), ("kept-group", 2)],
            [("removed-user", 1), ("kept-user", 2)],
        )
    monitor.last_tweet_ids = {"author": "100"}
    monitor.session = None
    first = True

    async def persist(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            monitor.config.x_monitor_mapping["author"] = (
                [] if remove_all else ["kept-group"]
            )
            monitor.config.x_monitor_user_mapping["author"] = (
                [] if remove_all else ["kept-user"]
            )

    monitor._persist_state = persist
    tweet = TweetItem(
        id="200",
        text="caption",
        created_at="",
        username="author",
        name="Author",
        url="",
    )
    assert await monitor._send_tweet_notification("author", tweet)
    if remove_all:
        monitor.sender.send_message.assert_not_awaited()
    else:
        assert monitor.sender.send_message.await_args.args[1:3] == (
            ["kept-group"],
            ["kept-user"],
        )
    assert monitor.last_tweet_ids["author"] == "200"
    assert not monitor._pending_tweet_delivery


@pytest.fixture
def x_reload_delivery(x_monitor_module, monkeypatch):
    from nonebot.adapters.onebot.v11 import MessageSegment

    from shared.adapter import outbound
    from utils.x_api.models import TweetItem

    monitor = x_monitor_module.XMonitor(
        SimpleNamespace(
            x_monitor_mapping={
                "author": ["current-group", "later-group", "kept-group"]
            },
            x_monitor_user_mapping={"author": ["later-user", "kept-user"]},
            x_at_all={},
        )
    )
    monitor.last_tweet_ids = {"author": "100"}
    monitor.sender = x_monitor_module.XSender()
    monitor.sender.build_tweet_message = MagicMock(
        return_value=Message(
            [
                MessageSegment.text("first"),
                MessageSegment.image(b"image"),
                MessageSegment.text("last"),
            ]
        )
    )
    monitor._persist_state = AsyncMock()
    bot = SimpleNamespace(send_to_group=AsyncMock(), send_to_c2c=AsyncMock())
    monkeypatch.setattr(outbound, "iter_official_bots", lambda: [bot])
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    monkeypatch.setattr(outbound, "_official_last_sent", {})
    monkeypatch.setattr(outbound, "_official_locks", {})
    monkeypatch.setitem(
        monitor.sender.send_message.__func__.__globals__,
        "messaging_bots",
        lambda: [bot],
    )
    tweet = TweetItem(
        id="200",
        text="caption",
        created_at="",
        username="author",
        name="Author",
        url="",
    )
    return monitor, bot, tweet, outbound


@pytest.mark.asyncio
@pytest.mark.parametrize("remove_current", [False, True])
@pytest.mark.parametrize("retry_kept", [False, True])
async def test_x_mapping_reload_after_ack_stops_removed_and_resumes_kept(
    x_reload_delivery, remove_current, retry_kept
):
    monitor, bot, tweet, _ = x_reload_delivery
    persisted = []

    async def persist(*args, **kwargs):
        persisted.append(monitor._pending_tweet_delivery.get("author"))
        if len(persisted) == 2:
            monitor.config.x_monitor_mapping["author"] = (
                [] if remove_current else ["current-group"]
            ) + ["kept-group"]
            monitor.config.x_monitor_user_mapping["author"] = ["kept-user"]
            await asyncio.sleep(0)

    monitor._persist_state = persist
    failed_once = False

    async def send_group(*, group_openid, message, msg_seq):
        nonlocal failed_once
        if (
            retry_kept
            and group_openid == "kept-group"
            and msg_seq == 2
            and not failed_once
        ):
            failed_once = True
            raise RuntimeError("temporary failure")

    bot.send_to_group.side_effect = send_group
    delivered = await monitor._send_tweet_notification(
        "author", tweet, check_generation=0
    )
    assert delivered is not retry_kept
    assert ("current-group", 1) in persisted[1][2]
    if retry_kept:
        assert monitor.last_tweet_ids["author"] == "100"
        assert monitor._pending_tweet_delivery["author"][2:] == (
            [("kept-group", 1)],
            [],
        )
        assert await monitor._send_tweet_notification(
            "author", tweet, check_generation=0
        )
    group_calls = bot.send_to_group.await_args_list
    assert not any(call.kwargs["group_openid"] == "later-group" for call in group_calls)
    assert [
        call.kwargs["msg_seq"]
        for call in group_calls
        if call.kwargs["group_openid"] == "current-group"
    ] == ([1] if remove_current else [1, 2, 3])
    assert [
        call.kwargs["msg_seq"]
        for call in group_calls
        if call.kwargs["group_openid"] == "kept-group"
    ] == ([1, 2, 2, 3] if retry_kept else [1, 2, 3])
    assert [call.kwargs["openid"] for call in bot.send_to_c2c.await_args_list] == [
        "kept-user"
    ] * 3
    assert monitor.last_tweet_ids["author"] == "200"
    assert not monitor._pending_tweet_delivery


@pytest.mark.asyncio
@pytest.mark.parametrize("wait_kind", ["pacing", "retry", "media"])
async def test_x_mapping_reload_during_official_wait_stops_api(
    x_reload_delivery, monkeypatch, wait_kind
):
    import time

    monitor, bot, tweet, outbound = x_reload_delivery
    sleep = asyncio.sleep

    def remove_targets():
        monitor.config.x_monitor_mapping["author"] = ["kept-group"]
        monitor.config.x_monitor_user_mapping["author"] = ["kept-user"]

    if wait_kind == "media":
        materialize = outbound._materialize_media
        first = True

        async def download(value):
            nonlocal first
            if first:
                first = False
                remove_targets()
                await sleep(0)
            return await materialize(value)

        monkeypatch.setattr(outbound, "_materialize_media", download)
    else:

        async def wait(_):
            remove_targets()
            await sleep(0)

        monkeypatch.setattr(outbound.asyncio, "sleep", wait)
        if wait_kind == "pacing":
            monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 3)
            outbound._official_last_sent["current-group"] = time.monotonic()
        else:

            async def reject(*, group_openid, message, msg_seq):
                if group_openid == "current-group":
                    raise RuntimeError("40034100")

            bot.send_to_group.side_effect = reject

    assert await monitor._send_tweet_notification("author", tweet, check_generation=0)
    assert [
        call.kwargs["msg_seq"]
        for call in bot.send_to_group.await_args_list
        if call.kwargs["group_openid"] == "current-group"
    ] == ([] if wait_kind == "pacing" else [1])
    assert not any(
        call.kwargs["group_openid"] == "later-group"
        for call in bot.send_to_group.await_args_list
    )
    assert [call.kwargs["openid"] for call in bot.send_to_c2c.await_args_list] == [
        "kept-user"
    ] * 3
    assert monitor.last_tweet_ids["author"] == "200"
    assert not monitor._pending_tweet_delivery


@pytest.mark.asyncio
async def test_x_mapping_reload_during_onebot_prefix_wait_stops_api(
    x_reload_delivery, monkeypatch
):
    monitor, _, tweet, outbound = x_reload_delivery
    monitor.config.x_monitor_mapping["author"] = ["1001", "1002"]
    monitor.config.x_monitor_user_mapping["author"] = []
    monitor.config.x_at_all = {"author": True}
    monitor.sender.build_tweet_message.return_value = Message("caption")
    bot = SimpleNamespace(send_group_msg=AsyncMock())
    sender_globals = monitor.sender.send_message.__func__.__globals__
    monkeypatch.setitem(sender_globals, "messaging_bots", lambda: [bot])
    monkeypatch.setitem(sender_globals, "iter_onebot_bots", lambda: [bot])
    monkeypatch.setattr(outbound, "iter_onebot_bots", lambda: [bot])

    async def prefix(*args, **kwargs):
        monitor.config.x_monitor_mapping["author"] = ["1002"]
        await asyncio.sleep(0)
        return Message("prefix")

    monkeypatch.setitem(sender_globals, "resolve_at_all_prefix", prefix)
    assert await monitor._send_tweet_notification("author", tweet, check_generation=0)
    assert [call.kwargs["group_id"] for call in bot.send_group_msg.await_args_list] == [
        1002,
        1002,
    ]
    assert not monitor._pending_tweet_delivery


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_x_plan_change_then_cancel_resets_offsets_before_persisting(
    x_monitor_module, monkeypatch, legacy
):
    from nonebot.adapters.onebot.v11 import MessageSegment

    from utils.x_api.models import TweetItem

    monitor = object.__new__(x_monitor_module.XMonitor)
    monitor.config = SimpleNamespace(
        x_monitor_mapping={"author": ["group-openid"]},
        x_monitor_user_mapping={"author": []},
        x_at_all={"author": True},
    )
    monitor.sender = x_monitor_module.XSender()
    message = Message([MessageSegment.text("caption"), MessageSegment.image(b"image")])
    monitor.sender.build_tweet_message = MagicMock(return_value=message)
    old_fp = (
        "ti"
        if legacy
        else monitor.sender.plan_fingerprint(message, at_all_enabled=False)
    )
    monitor._pending_tweet_delivery = {
        "author": ("200", old_fp, [("group-openid", 1)], [])
    }
    monitor.last_tweet_ids = {"author": "100"}
    monitor.session = None
    persisted = []

    async def persist(*args, **kwargs):
        persisted.append(monitor._pending_tweet_delivery["author"])
        raise asyncio.CancelledError

    monitor._persist_state = persist
    tweet = TweetItem(
        id="200",
        text="caption",
        created_at="",
        username="author",
        name="Author",
        url="",
    )
    with pytest.raises(asyncio.CancelledError):
        await monitor._send_tweet_notification("author", tweet)
    assert persisted[0][1] == monitor.sender.plan_fingerprint(
        message, at_all_enabled=True
    )
    assert persisted[0][2] == [("group-openid", 0)]
    monkeypatch.setitem(
        monitor.sender.send_to_groups.__func__.__globals__,
        "messaging_bots",
        lambda: [object()],
    )
    send = AsyncMock()
    monkeypatch.setitem(
        monitor.sender._send_official_batches.__func__.__globals__, "send_group", send
    )
    result = await monitor.sender.send_message(
        message,
        ["group-openid"],
        [],
        at_all_enabled=True,
        group_starts={"group-openid": 0},
        expected_fingerprint=persisted[0][1],
    )
    assert result.all_succeeded
    assert send.await_args.kwargs["start"] == 0
    assert "caption" in send.await_args.args[1].extract_plain_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["group", "user"])
@pytest.mark.parametrize("is_pinned", [False, True])
async def test_dynamic_official_partial_retry_keeps_snapshot_and_resumes_parts(
    scope,
    is_pinned,
    dynamic_monitor_module,
    dynamic_sender_module,
    monkeypatch,
):
    from nonebot.adapters.onebot.v11 import MessageSegment

    from shared.adapter import outbound
    from shared.adapter.qq_errors import LoggedQQApiError

    monitor = object.__new__(dynamic_monitor_module.DynamicMonitor)
    monitor.config = SimpleNamespace(
        dynamic_monitor_mapping={"111": ["group-openid"] if scope == "group" else []},
        dynamic_monitor_user_mapping={
            "111": ["user-openid"] if scope == "user" else []
        },
        dynamic_at_all={},
        enable_screenshot=True,
    )
    monitor._resolve_author_name = AsyncMock(return_value="author")
    monitor._fetch_dynamic_screenshot = AsyncMock(return_value=b"original-image")
    monitor._persist_state = AsyncMock()
    monitor.sender = dynamic_sender_module.DynamicSender()
    monitor.sender.build_dynamic_message = MagicMock(
        return_value=Message(
            [
                MessageSegment.text("original-caption"),
                MessageSegment.image(b"original-image"),
            ]
        )
    )
    accepted = []
    failed = False

    async def send(**kwargs):
        nonlocal failed
        message = kwargs["message"]
        segment = message[0]
        if segment.type == "file_image" and not failed:
            failed = True
            raise LoggedQQApiError(50055001, "临时发送失败")
        accepted.append(
            (
                segment.type,
                message.extract_plain_text()
                if segment.type == "text"
                else segment.data["content"],
            )
        )

    bot = SimpleNamespace(send_to_group=send, send_to_c2c=send)
    monkeypatch.setattr(outbound, "iter_official_bots", lambda: [bot])
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    dynamic = SimpleNamespace(id=200, uid="111", get_type_description=lambda: "text")
    assert not await monitor._send_dynamic_notification("111", dynamic, is_pinned)
    pending = monitor._pending_targets[("111", 200, is_pinned)]
    starts = pending.group_starts if scope == "group" else pending.user_starts
    assert starts[f"{scope}-openid"] == 1

    monitor.config.enable_screenshot = False
    monitor.config.dynamic_at_all["111"] = True
    monitor.sender.build_dynamic_message.return_value = Message("changed-template")
    assert await monitor._send_dynamic_notification("111", dynamic, is_pinned)
    assert accepted == [("text", "original-caption"), ("file_image", b"original-image")]
    monitor._fetch_dynamic_screenshot.assert_awaited_once()
    monitor.sender.build_dynamic_message.assert_called_once()
    completed = monitor._pending_targets[("111", 200, is_pinned)]
    assert not completed.groups and not completed.users


@pytest.mark.asyncio
async def test_live_official_targets_are_sent_alongside_onebot(live_monitor_module):
    from plugins.live_monitor.models import LiveRoomState
    from plugins.live_monitor.notification_delivery import LiveNotificationDelivery

    groups = ["official-group"]
    sender = SimpleNamespace(
        send_notification=AsyncMock(return_value=_delivery_succeeded())
    )
    delivery = LiveNotificationDelivery(
        sender,
        get_group_mapping=lambda: {"1": groups},
        get_user_mapping=lambda: {"1": ["official-user"]},
        get_at_all=lambda: {},
    )
    state = LiveRoomState(room_id=1)
    state.pending_start = True
    state.pending_start_groups = ["official-group"]
    assert await delivery.deliver_start("1", state, room_info=None, user_info=None)
    assert not state.pending_start
    sender.send_notification.assert_awaited_once()
    assert sender.send_notification.await_args.kwargs["target_groups"] == [
        "official-group"
    ]
    assert sender.send_notification.await_args.kwargs["target_users"] == []
    groups.append("1001")
    assert await delivery.deliver_start("1", state, room_info=None, user_info=None)
    assert sender.send_notification.await_args.kwargs["target_groups"] == [
        "official-group",
        "1001",
    ]
    assert sender.send_notification.await_args.kwargs["target_users"] == [
        "official-user"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get_latest_dynamic", "get_pinned_dynamic"])
@pytest.mark.parametrize("has_dynamic", [False, True])
async def test_dynamic_query_returns_message_for_event_reply(
    method, has_dynamic, dynamic_monitor_module
):
    monitor = object.__new__(dynamic_monitor_module.DynamicMonitor)
    monitor.config = SimpleNamespace(bilibili_cookie="", enable_screenshot=False)
    dynamic = SimpleNamespace(
        id=1,
        uid="123",
        timestamp=1,
        is_pinned=False,
        type=1,
        get_type_description=lambda: "text",
    )
    monitor.fetcher = SimpleNamespace(
        fetch_user_dynamics=AsyncMock(
            return_value=([dynamic], 1) if has_dynamic else ([], None)
        )
    )
    reply = Message("query result")
    monitor.sender = SimpleNamespace(
        build_dynamic_message=MagicMock(return_value=reply), send_to_groups=AsyncMock()
    )
    monitor._fetch_dynamic_screenshot = AsyncMock(return_value=None)
    monitor._resolve_author_name = AsyncMock(return_value="author")
    result = await getattr(monitor, method)("123")
    assert isinstance(result, Message)
    if has_dynamic:
        assert result == reply
    else:
        assert "暂无" in str(result)
    monitor.sender.send_to_groups.assert_not_awaited()


@pytest.mark.parametrize(
    ("targets", "all_succeeded", "any_succeeded", "all_failed"),
    [
        ([], False, False, False),
        ([TargetDelivery("group", "1", True)], True, True, False),
        ([TargetDelivery("group", "1", False, "err")], False, False, True),
        (
            [
                TargetDelivery("group", "1", True),
                TargetDelivery("user", "2", False, "err"),
            ],
            False,
            True,
            False,
        ),
    ],
)
def test_delivery_result_properties(
    targets, all_succeeded, any_succeeded, all_failed
) -> None:
    result = DeliveryResult(targets=targets)
    assert result.attempted == bool(targets)
    assert result.all_succeeded is all_succeeded
    assert result.any_succeeded is any_succeeded
    assert result.all_failed is all_failed


def test_aggregate_by_target_any_bot_success_counts_as_delivered() -> None:
    raw = DeliveryResult(
        targets=[
            TargetDelivery("group", "1001", True),
            TargetDelivery("group", "1001", False, "bot2 failed"),
            TargetDelivery("user", "2002", False, "bot1 failed"),
            TargetDelivery("user", "2002", True),
        ]
    )

    aggregated = aggregate_by_target(raw)

    assert len(aggregated.targets) == 2
    assert aggregated.all_succeeded
    assert all(target.success for target in aggregated.targets)


def test_aggregate_by_target_all_bots_failed_marks_target_failed() -> None:
    raw = DeliveryResult(
        targets=[
            TargetDelivery("group", "1001", False, "bot1 failed"),
            TargetDelivery("group", "1001", False, "bot2 failed"),
        ]
    )

    aggregated = aggregate_by_target(raw)

    assert len(aggregated.targets) == 1
    assert aggregated.all_failed
    assert aggregated.targets[0].error == "bot1 failed"


@pytest.mark.asyncio
async def test_dynamic_sender_no_bot_marks_all_targets_failed(
    dynamic_sender_module,
) -> None:
    sender = dynamic_sender_module.DynamicSender()
    driver = SimpleNamespace(bots={})
    with patch("nonebot.get_bots", return_value=driver.bots):
        result = await sender.send_message(Message("hi"), ["1001"], ["2002"])

    assert result.attempted
    assert result.all_failed
    assert len(result.targets) == 2
    assert all(not target.success for target in result.targets)


@pytest.mark.asyncio
async def test_dynamic_sender_all_targets_succeed(dynamic_sender_module) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = dynamic_sender_module.DynamicSender()
    bot = MagicMock(spec=Bot)
    bot.send_group_msg = AsyncMock()
    bot.send_private_msg = AsyncMock()
    driver = SimpleNamespace(bots={"bot": bot})

    with patch("nonebot.get_bots", return_value=driver.bots):
        result = await sender.send_message(Message("hi"), ["1001"], ["2002"])

    assert result.all_succeeded
    bot.send_group_msg.assert_awaited_once()
    bot.send_private_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_official_group_no_permission_logs_info() -> None:
    from shared.adapter.qq_errors import note_qq_api_error

    class Denied(Exception):
        code = 40034105
        message = "主动消息失败，无权限"

    with patch("shared.adapter.qq_errors.logger") as log:
        noted = note_qq_api_error(Denied(), target="GROUPOPENID")

    assert noted is not None
    assert noted.code == 40034105
    log.info.assert_called_once()
    log.warning.assert_not_called()
    log.opt.assert_not_called()


def test_qq_rate_limit_logs_warning() -> None:
    from shared.adapter.qq_errors import note_qq_api_error

    class Limited(Exception):
        code = 40034100
        message = "主动消息发送超过频控限制"

    with patch("shared.adapter.qq_errors.logger") as log:
        noted = note_qq_api_error(Limited(), target="GROUPOPENID")

    assert noted is not None
    log.warning.assert_called_once()
    log.info.assert_not_called()


@pytest.mark.parametrize(
    "error, terminal",
    [
        ("40034105 主动消息无权限", True),
        ("40034101 机器人不是群成员", True),
        ("40054003 机器人不是群成员", True),
        ("40034006 消息内容违规", True),
        ("40054007 消息长度超限", True),
        ("304036 无 Markdown 模板权限", True),
        ("22006 消息类型与内容不匹配", True),
        ("40034100 主动消息超过频控", False),
        ("40034004 富媒体转存失败", False),
        ("304080 文件信息无效", False),
        ("40054006 验证好友关系失败", False),
        ("40054016 机器人已下线", False),
        ("50055001 消息发送异常", False),
        ("50055002 消息发送异常", False),
        ("50055006 ARK 消息发送异常", False),
        ("999999 未知错误", False),
        ("down", False),
        (" ", False),
        (None, False),
    ],
)
def test_terminal_qq_error_text_matches_documented_rejection(error, terminal) -> None:
    from shared.adapter.qq_errors import is_terminal_qq_error_text

    assert is_terminal_qq_error_text(error) is terminal


def test_terminal_content_rejection_keeps_warning_log() -> None:
    from shared.adapter.qq_errors import is_terminal_qq_error_text, note_qq_api_error

    class Rejected(Exception):
        code = 40034006
        message = "消息内容违规"

    with patch("shared.adapter.qq_errors.logger") as log:
        noted = note_qq_api_error(Rejected(), target="GROUPOPENID")

    assert noted is not None
    assert is_terminal_qq_error_text(str(noted))
    log.warning.assert_called_once()
    log.info.assert_not_called()


def test_c2c_user_reject_logs_info() -> None:
    from shared.adapter.qq_errors import note_qq_api_error

    class Rejected(Exception):
        code = 40054013
        message = "用户拒收消息"

    with patch("shared.adapter.qq_errors.logger") as log:
        noted = note_qq_api_error(Rejected(), target="USEROPENID")

    assert noted is not None
    assert noted.code == 40054013
    log.info.assert_called_once()
    log.warning.assert_not_called()


@pytest.mark.asyncio
async def test_dynamic_sender_partial_failure(dynamic_sender_module) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = dynamic_sender_module.DynamicSender()
    bot = MagicMock(spec=Bot)
    bot.send_group_msg = AsyncMock(side_effect=RuntimeError("send failed"))
    bot.send_private_msg = AsyncMock()
    driver = SimpleNamespace(bots={"bot": bot})

    with patch("nonebot.get_bots", return_value=driver.bots):
        result = await sender.send_message(Message("hi"), ["1001"], ["2002"])

    assert result.any_succeeded
    assert not result.all_succeeded
    assert result.targets[0].success is False
    assert result.targets[1].success is True


@pytest.mark.asyncio
async def test_dynamic_sender_any_bot_success_counts_as_delivered(
    dynamic_sender_module,
) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = dynamic_sender_module.DynamicSender()
    failing_bot = MagicMock(spec=Bot)
    failing_bot.send_group_msg = AsyncMock(side_effect=RuntimeError("not in group"))
    succeeding_bot = MagicMock(spec=Bot)
    succeeding_bot.send_group_msg = AsyncMock()
    driver = SimpleNamespace(bots={"a": failing_bot, "b": succeeding_bot})

    with patch("nonebot.get_bots", return_value=driver.bots):
        result = await sender.send_to_groups(Message("hi"), ["1001"])

    assert len(result.targets) == 1
    assert result.all_succeeded
    failing_bot.send_group_msg.assert_awaited_once()
    succeeding_bot.send_group_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_dynamic_sender_does_not_duplicate_when_first_bot_succeeds(
    dynamic_sender_module,
) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = dynamic_sender_module.DynamicSender()
    first_bot = MagicMock(spec=Bot)
    first_bot.send_group_msg = AsyncMock()
    second_bot = MagicMock(spec=Bot)
    second_bot.send_group_msg = AsyncMock()
    driver = SimpleNamespace(bots={"a": first_bot, "b": second_bot})

    with patch("nonebot.get_bots", return_value=driver.bots):
        result = await sender.send_to_groups(Message("hi"), ["1001"])

    assert result.all_succeeded
    first_bot.send_group_msg.assert_awaited_once()
    second_bot.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["start", "end"])
async def test_live_sender_no_bot_marks_targets_failed(
    live_sender_module, status
) -> None:
    sender = live_sender_module.LiveNotificationSender()
    driver = SimpleNamespace(bots={})

    async def filter_targets(pending):
        pending.groups = ["1001"]

    prepared = AsyncMock(side_effect=filter_targets)
    with (
        patch("nonebot.get_bots", return_value=driver.bots),
        patch.object(sender, "_generate_card_if_needed", AsyncMock(return_value=None)),
        patch.object(sender, "_send_group_message", AsyncMock()) as send_group,
        patch.object(sender, "_send_private_message", AsyncMock()) as send_user,
    ):
        result = await sender.send_notification(
            status=status,
            streamer_name="tester",
            room_info=None,
            target_groups=["1001", "removed"],
            target_users=["2002"],
            on_prepared=prepared,
        )

    prepared.assert_awaited_once()
    assert "tester" in prepared.await_args.args[0].message.extract_plain_text()
    assert result.all_failed
    assert [target.target_id for target in result.targets] == ["1001", "2002"]
    send_group.assert_not_awaited()
    send_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_sender_partial_failure(live_sender_module) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = live_sender_module.LiveNotificationSender()
    bot = MagicMock(spec=Bot)
    bot.send_group_msg = AsyncMock(side_effect=RuntimeError("group failed"))
    bot.send_private_msg = AsyncMock()
    driver = SimpleNamespace(bots={"bot": bot})

    with (
        patch("nonebot.get_bots", return_value=driver.bots),
        patch.object(sender, "_generate_card_if_needed", AsyncMock(return_value=None)),
    ):
        result = await sender.send_notification(
            status="start",
            streamer_name="tester",
            room_info=None,
            target_groups=["1001"],
            target_users=["2002"],
            at_all_enabled=False,
        )

    assert result.any_succeeded
    assert not result.all_succeeded


@pytest.mark.asyncio
async def test_live_sender_any_bot_success_counts_as_delivered(
    live_sender_module,
) -> None:
    """首个 Bot 失败时应 failover 到下一个 Bot，最终仍算投递成功。"""
    from nonebot.adapters.onebot.v11 import Bot

    sender = live_sender_module.LiveNotificationSender()
    bot_fail = MagicMock(spec=Bot)
    bot_fail.send_group_msg = AsyncMock(side_effect=RuntimeError("no access"))
    bot_fail.send_private_msg = AsyncMock(side_effect=RuntimeError("no access"))
    bot_ok = MagicMock(spec=Bot)
    bot_ok.send_group_msg = AsyncMock()
    bot_ok.send_private_msg = AsyncMock()
    driver = SimpleNamespace(bots={"fail": bot_fail, "ok": bot_ok})

    with (
        patch("nonebot.get_bots", return_value=driver.bots),
        patch.object(sender, "_generate_card_if_needed", AsyncMock(return_value=None)),
    ):
        result = await sender.send_notification(
            status="start",
            streamer_name="tester",
            room_info=None,
            target_groups=["1001"],
            target_users=[],
            at_all_enabled=False,
        )

    assert len(result.targets) == 1
    assert result.all_succeeded
    bot_fail.send_group_msg.assert_awaited_once()
    bot_ok.send_group_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_live_sender_does_not_duplicate_when_first_bot_succeeds(
    live_sender_module,
) -> None:
    """多 Bot 同群时，首个 Bot 成功后不应再向第二个 Bot 重复投递。"""
    from nonebot.adapters.onebot.v11 import Bot

    sender = live_sender_module.LiveNotificationSender()
    first_bot = MagicMock(spec=Bot)
    first_bot.send_group_msg = AsyncMock()
    second_bot = MagicMock(spec=Bot)
    second_bot.send_group_msg = AsyncMock()
    driver = SimpleNamespace(bots={"a": first_bot, "b": second_bot})

    with (
        patch("nonebot.get_bots", return_value=driver.bots),
        patch.object(sender, "_generate_card_if_needed", AsyncMock(return_value=None)),
    ):
        result = await sender.send_notification(
            status="start",
            streamer_name="tester",
            room_info=None,
            target_groups=["1001"],
            target_users=[],
            at_all_enabled=False,
        )

    assert result.all_succeeded
    first_bot.send_group_msg.assert_awaited_once()
    second_bot.send_group_msg.assert_not_awaited()


def _room_info(live_models_module, status):
    from utils.bilibili_api import RoomInfo

    return RoomInfo(
        uid=2,
        room_id=1,
        short_room_id=1,
        area_id=1,
        area_name="area",
        parent_area_id=1,
        parent_area_name="parent",
        live_status=status,
        live_start_time=100,
        online=0,
        title="title",
        cover="",
    )


def test_live_room_state_detect_without_mutating_previous_status(
    live_models_module,
) -> None:
    from utils.bilibili_api import LiveStatus

    state = live_models_module.LiveRoomState(
        room_id=1, previous_status=LiveStatus.PREPARING
    )
    began, ended, new_status, start_time = state.detect_status_change(
        _room_info(live_models_module, LiveStatus.LIVE)
    )

    assert began is True
    assert ended is False
    assert new_status == LiveStatus.LIVE
    assert start_time == 100
    assert state.previous_status == LiveStatus.PREPARING


def test_live_room_state_apply_status_after_delivery(live_models_module) -> None:
    from utils.bilibili_api import LiveStatus

    state = live_models_module.LiveRoomState(
        room_id=1, previous_status=LiveStatus.PREPARING
    )
    room_info = _room_info(live_models_module, LiveStatus.LIVE)

    state.sync_observed_status(room_info, LiveStatus.LIVE, start_time=100)

    assert state.previous_status == LiveStatus.LIVE
    assert state.room_info == room_info
    assert state.start_time == 100


def test_live_room_state_pending_flags_track_undelivered_notifications(
    live_models_module,
) -> None:
    state = live_models_module.LiveRoomState(room_id=1)
    state.pending_start = True
    state.pending_end = True

    assert state.pending_start is True
    assert state.pending_end is True


@pytest.mark.asyncio
async def test_dynamic_monitor_does_not_advance_cursor_when_send_fails(
    dynamic_monitor_module,
) -> None:
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    config = SimpleNamespace(
        dynamic_monitor_mapping={"123": ["1001"]},
        dynamic_monitor_user_mapping={},
        dynamic_at_all={},
        bilibili_cookie="",
        enable_screenshot=False,
    )
    monitor = DynamicMonitor(config)
    monitor.is_running = True
    monitor.initialized_uids["123"] = True
    monitor.last_dynamic_ids["123"] = 10
    monitor.pinned_dynamic_ids["123"] = None
    monitor._check_generation["123"] = 0
    monitor.fetcher = MagicMock()
    monitor.sender = MagicMock()
    monitor.sender.build_dynamic_message = MagicMock(return_value=Message("hi"))
    monitor.sender.send_message = AsyncMock(
        return_value=DeliveryResult(
            targets=[TargetDelivery("group", "1001", False, "offline")]
        )
    )

    dynamic = SimpleNamespace(
        id=11,
        uid=123,
        name="tester",
        timestamp=1,
        get_type_description=MagicMock(return_value="图文"),
    )
    monitor.fetcher.resolve_user_name = AsyncMock(return_value="tester")
    monitor.fetcher.fetch_user_dynamics = AsyncMock(return_value=([dynamic], None))
    monitor._persist_state = AsyncMock()

    ok = await monitor._check_user_dynamic("123")
    await monitor._drain_pending_deliveries()

    assert ok is True
    assert monitor.last_dynamic_ids["123"] == 10
    monitor._persist_state.assert_awaited_with("123", check_generation=0)
    assert monitor._pending_targets[("123", 11, False)].groups == ["1001"]


@pytest.mark.asyncio
async def test_dynamic_monitor_advances_cursor_when_send_succeeds(
    dynamic_monitor_module,
) -> None:
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    config = SimpleNamespace(
        dynamic_monitor_mapping={"123": ["1001"]},
        dynamic_monitor_user_mapping={},
        dynamic_at_all={},
        bilibili_cookie="",
        enable_screenshot=False,
    )
    monitor = DynamicMonitor(config)
    monitor.is_running = True
    monitor.initialized_uids["123"] = True
    monitor.last_dynamic_ids["123"] = 10
    monitor.pinned_dynamic_ids["123"] = None
    monitor._check_generation["123"] = 0
    monitor.fetcher = MagicMock()
    monitor.sender = MagicMock()
    monitor.sender.build_dynamic_message = MagicMock(return_value=Message("hi"))
    monitor.sender.send_message = AsyncMock(
        return_value=DeliveryResult(targets=[TargetDelivery("group", "1001", True)])
    )

    dynamic = SimpleNamespace(
        id=11,
        uid=123,
        name="tester",
        timestamp=1,
        get_type_description=MagicMock(return_value="图文"),
    )
    monitor.fetcher.resolve_user_name = AsyncMock(return_value="tester")
    monitor.fetcher.fetch_user_dynamics = AsyncMock(return_value=([dynamic], None))
    monitor._persist_state = AsyncMock()

    ok = await monitor._check_user_dynamic("123")
    await monitor._drain_pending_deliveries()

    assert ok is True
    assert monitor.last_dynamic_ids["123"] == 11
    monitor._persist_state.assert_awaited_with("123", check_generation=0)
    assert not monitor._pending_targets


@pytest.mark.asyncio
async def test_end_notification_sent_after_start_delivery_failed(
    live_monitor_module,
) -> None:
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=False,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus):
            self.live_status = status
            self.live_start_time = 1000
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    live_room = FakeRoomInfo(LiveStatus.LIVE)
    end_room = FakeRoomInfo(LiveStatus.PREPARING)
    fetch_results = iter([(live_room, None), (end_room, None)])

    async def fetch_room(*_args, **_kwargs):
        return next(fetch_results)

    send_mock = AsyncMock(
        side_effect=[
            _delivery_failed(),
            _delivery_succeeded(),
            _delivery_succeeded(),
        ]
    )

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._check_room_status("111")
        await monitor._check_room_status("111")

    assert state.previous_status == LiveStatus.PREPARING
    assert state.pending_start is False
    assert state.pending_end is False
    assert send_mock.await_count == 3
    assert send_mock.await_args_list[0].args[1] == "start"
    assert send_mock.await_args_list[1].args[1] == "start"
    assert send_mock.await_args_list[2].args[1] == "end"


@pytest.mark.asyncio
async def test_pending_start_flushed_before_end_on_websocket_short_stream(
    live_monitor_module,
) -> None:
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    state.room_info = SimpleNamespace(
        live_status=LiveStatus.LIVE,
        live_start_time=1000,
        title="title",
        cover="",
    )
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus):
            self.live_status = status
            self.live_start_time = 1000
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    live_room = FakeRoomInfo(LiveStatus.LIVE)
    end_room = FakeRoomInfo(LiveStatus.PREPARING)
    fetch_results = iter([(live_room, None), (end_room, None)])

    async def fetch_room(*_args, **_kwargs):
        return next(fetch_results)

    send_mock = AsyncMock(
        side_effect=[
            _delivery_failed(),
            _delivery_succeeded(),
            _delivery_succeeded(),
        ]
    )

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._handle_live_signal("111")
        assert state.pending_start is True
        assert state.previous_status == LiveStatus.LIVE

        await monitor._handle_preparing_signal("111", round_status=None)

    assert state.pending_start is False
    assert state.pending_end is False
    assert state.previous_status == LiveStatus.PREPARING
    assert send_mock.await_count == 3
    assert send_mock.await_args_list[0].args[1] == "start"
    assert send_mock.await_args_list[1].args[1] == "start"
    assert send_mock.await_args_list[2].args[1] == "end"


@pytest.mark.asyncio
async def test_live_signal_delivers_end_when_api_already_offline(
    live_monitor_module,
) -> None:
    """API 已下播时收到延迟 LIVE 信号，仍应投递关播通知。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.LIVE)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 1000
        title = "title"
        cover = ""

    send_mock = AsyncMock(return_value=_delivery_succeeded())

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._handle_live_signal("111")

    assert state.previous_status == LiveStatus.PREPARING
    assert send_mock.await_count == 1
    assert send_mock.await_args_list[0].args[1] == "end"


@pytest.mark.asyncio
async def test_pending_start_retried_while_room_stays_live(
    live_monitor_module,
) -> None:
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=False,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.LIVE
        live_start_time = 1000
        title = "title"
        cover = ""

    send_mock = AsyncMock(side_effect=[_delivery_failed(), _delivery_succeeded()])

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._check_room_status("111")
        await monitor._check_room_status("111")

    assert state.previous_status == LiveStatus.LIVE
    assert state.pending_start is False
    assert send_mock.await_count == 2
    assert all(call.args[1] == "start" for call in send_mock.await_args_list)


@pytest.mark.asyncio
async def test_pending_start_retry_only_targets_failed_groups(
    live_monitor_module,
) -> None:
    """部分投递失败时，重试只应向未成功的群组发送，避免重复推送。"""
    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001", "1002"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=False,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111)
    monitor.room_states["111"] = state

    partial = DeliveryResult(
        targets=[
            TargetDelivery("group", "1001", True),
            TargetDelivery("group", "1002", False, "offline"),
        ]
    )
    success = DeliveryResult(targets=[TargetDelivery("group", "1002", True)])
    send_notify = AsyncMock(side_effect=[partial, success])

    with patch.object(monitor._sender, "send_notification", send_notify):
        first_ok = await monitor._delivery.deliver_start(
            "111",
            state,
            room_info=SimpleNamespace(title="title", cover=""),
            user_info=None,
        )
        second_ok = await monitor._delivery.deliver_start(
            "111",
            state,
            room_info=SimpleNamespace(title="title", cover=""),
            user_info=None,
        )

    assert first_ok is False
    assert second_ok is True
    assert state.pending_start is False
    assert state.pending_start_groups == []
    assert send_notify.await_count == 2
    assert send_notify.await_args_list[0].kwargs["target_groups"] == ["1001", "1002"]
    assert send_notify.await_args_list[1].kwargs["target_groups"] == ["1002"]
    assert send_notify.await_args_list[1].kwargs["target_users"] == []


@pytest.mark.asyncio
async def test_pending_end_retry_only_targets_failed_groups(
    live_monitor_module,
) -> None:
    """部分下播投递失败时，重试只应向未成功的群组发送，避免重复推送。"""
    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001", "1002"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=False,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111)
    monitor.room_states["111"] = state

    partial = DeliveryResult(
        targets=[
            TargetDelivery("group", "1001", True),
            TargetDelivery("group", "1002", False, "offline"),
        ]
    )
    success = DeliveryResult(targets=[TargetDelivery("group", "1002", True)])
    send_notify = AsyncMock(side_effect=[partial, success])

    with patch.object(monitor._sender, "send_notification", send_notify):
        first_ok = await monitor._delivery.deliver_end(
            "111",
            state,
            room_info=SimpleNamespace(title="title", cover=""),
            user_info=None,
        )
        second_ok = await monitor._delivery.deliver_end(
            "111",
            state,
            room_info=SimpleNamespace(title="title", cover=""),
            user_info=None,
        )

    assert first_ok is False
    assert second_ok is True
    assert state.pending_end is False
    assert state.pending_end_groups == []
    assert send_notify.await_count == 2
    assert send_notify.await_args_list[0].kwargs["status"] == "end"
    assert send_notify.await_args_list[0].kwargs["target_groups"] == ["1001", "1002"]
    assert send_notify.await_args_list[1].kwargs["target_groups"] == ["1002"]
    assert send_notify.await_args_list[1].kwargs["target_users"] == []


@pytest.mark.asyncio
async def test_pending_start_retry_only_targets_failed_users(
    live_monitor_module,
) -> None:
    """群组与用户混合配置时，重试只应向未成功的用户发送。"""
    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={"111": ["2001", "2002"]},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=False,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111)
    monitor.room_states["111"] = state

    partial = DeliveryResult(
        targets=[
            TargetDelivery("group", "1001", True),
            TargetDelivery("user", "2001", True),
            TargetDelivery("user", "2002", False, "offline"),
        ]
    )
    success = DeliveryResult(targets=[TargetDelivery("user", "2002", True)])
    send_notify = AsyncMock(side_effect=[partial, success])

    with patch.object(monitor._sender, "send_notification", send_notify):
        first_ok = await monitor._delivery.deliver_start(
            "111",
            state,
            room_info=SimpleNamespace(title="title", cover=""),
            user_info=None,
        )
        second_ok = await monitor._delivery.deliver_start(
            "111",
            state,
            room_info=SimpleNamespace(title="title", cover=""),
            user_info=None,
        )

    assert first_ok is False
    assert second_ok is True
    assert state.pending_start is False
    assert state.pending_start_users == []
    assert send_notify.await_count == 2
    assert send_notify.await_args_list[0].kwargs["target_groups"] == ["1001"]
    assert send_notify.await_args_list[0].kwargs["target_users"] == ["2001", "2002"]
    assert send_notify.await_args_list[1].kwargs["target_groups"] == []
    assert send_notify.await_args_list[1].kwargs["target_users"] == ["2002"]


@pytest.mark.asyncio
async def test_pending_end_cleared_when_new_live_begins_before_retry(
    live_monitor_module,
) -> None:
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=False,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.LIVE)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus):
            self.live_status = status
            self.live_start_time = 1000
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    end_room = FakeRoomInfo(LiveStatus.PREPARING)
    live_room = FakeRoomInfo(LiveStatus.LIVE)
    fetch_results = iter([(end_room, None), (live_room, None)])

    async def fetch_room(*_args, **_kwargs):
        return next(fetch_results)

    send_mock = AsyncMock(side_effect=[_delivery_failed(), _delivery_succeeded()])

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._check_room_status("111")
        assert state.pending_end is True
        assert state.previous_status == LiveStatus.PREPARING

        await monitor._check_room_status("111")

    assert state.pending_end is False
    assert state.pending_end_groups == []
    assert state.previous_status == LiveStatus.LIVE
    assert send_mock.await_count == 2
    assert send_mock.await_args_list[0].args[1] == "end"
    assert send_mock.await_args_list[1].args[1] == "start"


@pytest.mark.asyncio
async def test_pending_end_cleared_when_websocket_live_signal_before_retry(
    live_monitor_module,
) -> None:
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.LIVE)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus):
            self.live_status = status
            self.live_start_time = 1000
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    end_room = FakeRoomInfo(LiveStatus.PREPARING)
    live_room = FakeRoomInfo(LiveStatus.LIVE)
    fetch_results = iter([(end_room, None), (live_room, None)])

    async def fetch_room(*_args, **_kwargs):
        return next(fetch_results)

    send_mock = AsyncMock(side_effect=[_delivery_failed(), _delivery_succeeded()])

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._handle_preparing_signal("111", round_status=None)
        assert state.pending_end is True
        assert state.previous_status == LiveStatus.PREPARING

        await monitor._handle_live_signal("111")

    assert state.pending_end is False
    assert state.pending_end_groups == []
    assert state.previous_status == LiveStatus.LIVE
    assert send_mock.await_count == 2
    assert send_mock.await_args_list[0].args[1] == "end"
    assert send_mock.await_args_list[1].args[1] == "start"


@pytest.mark.asyncio
async def test_websocket_and_poll_do_not_double_deliver_end(
    live_monitor_module,
) -> None:
    """WS 关播投递未完成时轮询不得再发一次下播通知。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.LIVE, start_time=1000)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 1000
        title = "title"
        cover = ""

        def is_living(self) -> bool:
            return False

    send_started = asyncio.Event()
    release_send = asyncio.Event()
    send_calls = 0

    async def slow_send(*_args, **_kwargs):
        nonlocal send_calls
        send_calls += 1
        send_started.set()
        await release_send.wait()
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=slow_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        ws_task = asyncio.create_task(
            monitor._handle_preparing_signal("111", round_status=1)
        )
        await send_started.wait()
        assert state.previous_status == LiveStatus.PREPARING

        # 轮询可能在 retry_pending 上等待同一把房间锁，须先放行 WS 投递
        poll_task = asyncio.create_task(monitor._check_room_status("111"))
        await asyncio.sleep(0)
        assert send_calls == 1
        release_send.set()
        await ws_task
        await poll_task

    assert send_calls == 1
    assert state.previous_status == LiveStatus.PREPARING
    assert state.pending_end is False


@pytest.mark.asyncio
async def test_websocket_and_poll_do_not_double_deliver_start(
    live_monitor_module,
) -> None:
    """WS 开播投递未完成时轮询不得再发一次开播通知。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.LIVE
        live_start_time = 1000
        title = "title"
        cover = ""

        def is_living(self) -> bool:
            return True

    send_started = asyncio.Event()
    release_send = asyncio.Event()
    send_calls = 0

    async def slow_send(*_args, **_kwargs):
        nonlocal send_calls
        send_calls += 1
        send_started.set()
        await release_send.wait()
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=slow_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        ws_task = asyncio.create_task(monitor._handle_live_signal("111"))
        await send_started.wait()
        assert state.previous_status == LiveStatus.LIVE

        poll_task = asyncio.create_task(monitor._check_room_status("111"))
        await asyncio.sleep(0)
        assert send_calls == 1
        release_send.set()
        await ws_task
        await poll_task

    assert send_calls == 1
    assert state.previous_status == LiveStatus.LIVE
    assert state.pending_start is False


@pytest.mark.asyncio
async def test_end_waits_for_in_flight_start_before_flushing_pending(
    live_monitor_module,
) -> None:
    """短播关播须等开播投递结束，才能看到 pending_start 并补发。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus, *, live_start_time: int = 1000):
            self.live_status = status
            self.live_start_time = live_start_time
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    live_room = FakeRoomInfo(LiveStatus.LIVE, live_start_time=12345)
    end_room = FakeRoomInfo(LiveStatus.PREPARING, live_start_time=0)
    fetch_results = iter([(live_room, None), (end_room, None)])

    async def fetch_room(*_args, **_kwargs):
        return next(fetch_results)

    start_started = asyncio.Event()
    release_start = asyncio.Event()
    statuses: list[str] = []

    async def gated_send(_room_id, status, *_args, **kwargs):
        statuses.append(status)
        if status == "start" and len(statuses) == 1:
            start_started.set()
            await release_start.wait()
            return _delivery_failed()
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=gated_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        start_task = asyncio.create_task(monitor._handle_live_signal("111"))
        await start_started.wait()
        assert state.previous_status == LiveStatus.LIVE
        assert state.pending_start is True

        end_task = asyncio.create_task(
            monitor._handle_preparing_signal("111", round_status=None)
        )
        await asyncio.sleep(0)
        assert "end" not in statuses

        release_start.set()
        await start_task
        await end_task

    assert statuses == ["start", "start", "end"]
    assert state.pending_start is False
    assert state.pending_end is False
    assert state.previous_status == LiveStatus.PREPARING


@pytest.mark.asyncio
async def test_pending_start_flush_keeps_live_snapshot_after_end_confirm(
    live_monitor_module,
) -> None:
    """关播确认用离线快照后，补发 start 仍应使用直播中的 room_info。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    live_snapshot = SimpleNamespace(
        live_status=LiveStatus.LIVE,
        live_start_time=12345,
        title="live-title",
        cover="cover",
    )
    state = LiveRoomState(
        room_id=111,
        previous_status=LiveStatus.LIVE,
        room_info=live_snapshot,
        start_time=12345,
        pending_start=True,
        pending_start_groups=["1001"],
    )
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class OfflineRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 0
        title = "offline"
        cover = ""

        def is_living(self) -> bool:
            return False

    seen_start_rooms: list[object] = []

    async def capture_send(_room_id, status, *_args, **kwargs):
        if status == "start":
            seen_start_rooms.append(kwargs.get("room_info"))
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(OfflineRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=capture_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._handle_preparing_signal("111", round_status=None)

    assert seen_start_rooms == [live_snapshot]
    assert getattr(seen_start_rooms[0], "live_start_time") == 12345
    assert state.pending_start is False
    assert state.previous_status == LiveStatus.PREPARING


@pytest.mark.asyncio
async def test_start_delivery_exception_marks_pending_for_retry(
    live_monitor_module,
) -> None:
    """confirm 后投递抛异常时须留下 pending_start，否则永远不会重试。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.LIVE
        live_start_time = 1000
        title = "title"
        cover = ""

        def is_living(self) -> bool:
            return True

    send_mock = AsyncMock(side_effect=[RuntimeError("boom"), _delivery_succeeded()])

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._handle_live_signal("111")
        assert state.previous_status == LiveStatus.LIVE
        assert state.pending_start is True

        await monitor._check_room_status("111")

    assert state.pending_start is False
    assert send_mock.await_count == 2
    assert all(call.args[1] == "start" for call in send_mock.await_args_list)


@pytest.mark.asyncio
async def test_end_delivery_exception_marks_pending_for_retry(
    live_monitor_module,
) -> None:
    """confirm 后下播投递抛异常时须留下 pending_end，否则永远不会重试。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.LIVE, start_time=1000)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 0
        title = "title"
        cover = ""

        def is_living(self) -> bool:
            return False

    send_mock = AsyncMock(side_effect=[RuntimeError("boom"), _delivery_succeeded()])

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._handle_preparing_signal("111", round_status=None)
        assert state.previous_status == LiveStatus.PREPARING
        assert state.pending_end is True

        await monitor._check_room_status("111")

    assert state.pending_end is False
    assert send_mock.await_count == 2
    assert all(call.args[1] == "end" for call in send_mock.await_args_list)


@pytest.mark.asyncio
async def test_start_delivery_cancellation_marks_pending_then_reraises(
    live_monitor_module,
) -> None:
    """任务取消须在 confirm 后留下 pending_start，并继续向上抛出。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.LIVE
        live_start_time = 1000
        title = "title"
        cover = ""

        def is_living(self) -> bool:
            return True

    async def cancel_send(*_args, **_kwargs):
        raise asyncio.CancelledError()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=cancel_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await monitor._handle_live_signal("111")

    assert state.previous_status == LiveStatus.LIVE
    assert state.pending_start is True


@pytest.mark.asyncio
async def test_end_delivery_cancellation_marks_pending_then_reraises(
    live_monitor_module,
) -> None:
    """任务取消须在 confirm 后留下 pending_end，并继续向上抛出。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.LIVE, start_time=1000)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 0
        title = "title"
        cover = ""

        def is_living(self) -> bool:
            return False

    async def cancel_send(*_args, **_kwargs):
        raise asyncio.CancelledError()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=cancel_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await monitor._handle_preparing_signal("111", round_status=None)

    assert state.previous_status == LiveStatus.PREPARING
    assert state.pending_end is True


@pytest.mark.asyncio
async def test_stale_poll_snapshot_does_not_end_after_websocket_start(
    live_monitor_module,
) -> None:
    """轮询持有过期 PREPARING 快照时，不得在 WS 开播后再发关播。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus):
            self.live_status = status
            self.live_start_time = 1000 if status == LiveStatus.LIVE else 0
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    poll_release = asyncio.Event()
    poll_holding = asyncio.Event()
    statuses: list[str] = []

    async def fetch_room(*_args, **_kwargs):
        # 第一次：轮询拿到过期 PREPARING；第二次：WS 拿到 LIVE
        if not poll_holding.is_set():
            poll_holding.set()
            await poll_release.wait()
            return FakeRoomInfo(LiveStatus.PREPARING), None
        return FakeRoomInfo(LiveStatus.LIVE), None

    async def record_send(_room_id, status, *_args, **_kwargs):
        statuses.append(status)
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=record_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        poll_task = asyncio.create_task(monitor._check_room_status("111"))
        await poll_holding.wait()
        await monitor._handle_live_signal("111")
        assert state.previous_status == LiveStatus.LIVE
        poll_release.set()
        await poll_task

    assert statuses == ["start"]
    assert state.previous_status == LiveStatus.LIVE
    assert state.pending_end is False


@pytest.mark.asyncio
async def test_cancel_during_pre_end_flush_keeps_start_and_end_retryable(
    live_monitor_module,
) -> None:
    """关播 confirm 后补发 start 被取消时，start/end 均应可在后续轮询重试。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    live_snapshot = SimpleNamespace(
        live_status=LiveStatus.LIVE,
        live_start_time=12345,
        title="live-title",
        cover="cover",
    )
    state = LiveRoomState(
        room_id=111,
        previous_status=LiveStatus.LIVE,
        room_info=live_snapshot,
        start_time=12345,
        pending_start=True,
        pending_start_groups=["1001"],
        last_live_room_info=live_snapshot,
    )
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class OfflineRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 0
        title = "offline"
        cover = ""

        def is_living(self) -> bool:
            return False

    call_n = 0
    statuses: list[str] = []

    async def send_side_effect(_room_id, status, *_args, **kwargs):
        nonlocal call_n
        call_n += 1
        statuses.append(status)
        if call_n == 1:
            raise asyncio.CancelledError()
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(OfflineRoomInfo(), None),
        ),
        patch.object(
            monitor._delivery, "_send_notification", side_effect=send_side_effect
        ),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await monitor._handle_preparing_signal("111", round_status=None)

        assert state.previous_status == LiveStatus.PREPARING
        assert state.pending_start is True
        assert state.pending_end is True

        await monitor._check_room_status("111")

    assert statuses == ["start", "start", "end"]
    assert state.pending_start is False
    assert state.pending_end is False


@pytest.mark.asyncio
async def test_stale_poll_retry_uses_last_live_snapshot_for_pending_start(
    live_monitor_module,
) -> None:
    """过期轮询触发 pending start 重试时，须用 last_live 快照而非离线 API 快照。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    live_snapshot = SimpleNamespace(
        live_status=LiveStatus.LIVE,
        live_start_time=12345,
        title="live-title",
        cover="cover",
    )
    state = LiveRoomState(
        room_id=111,
        previous_status=LiveStatus.LIVE,
        room_info=live_snapshot,
        start_time=12345,
        observation_epoch=1,
        pending_start=True,
        pending_start_groups=["1001"],
        last_live_room_info=live_snapshot,
    )
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class OfflineRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 0
        title = "stale-offline"
        cover = ""

        def is_living(self) -> bool:
            return False

    seen_rooms: list[object] = []

    async def capture_send(_room_id, status, *_args, **kwargs):
        if status == "start":
            seen_rooms.append(kwargs.get("room_info"))
        return _delivery_succeeded()

    # 人为制造：fetch 前 epoch 被并发 +1，走 stale 分支
    state.observation_epoch = 1
    original_epoch = state.observation_epoch

    async def fetch_and_bump(*_args, **_kwargs):
        state.observation_epoch = original_epoch + 1
        return OfflineRoomInfo(), None

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_and_bump,
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=capture_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        # check 开始时记下 epoch=1，fetch 中被 bump 到 2 → stale
        ok = await monitor._check_room_status("111")

    assert ok is True
    assert seen_rooms == [live_snapshot]
    assert getattr(seen_rooms[0], "live_start_time") == 12345
    assert state.pending_start is False


@pytest.mark.asyncio
async def test_websocket_live_after_poll_end_still_delivers_start(
    live_monitor_module,
) -> None:
    """轮询先确认关播抬升 epoch 后，已在途的 WS LIVE 快照仍应开播投递。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.LIVE, start_time=1000)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus, *, live_start_time: int):
            self.live_status = status
            self.live_start_time = live_start_time
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    ws_holding = asyncio.Event()
    ws_release = asyncio.Event()
    statuses: list[str] = []
    fetch_n = 0

    async def fetch_room(*_args, **_kwargs):
        nonlocal fetch_n
        fetch_n += 1
        if fetch_n == 1:
            # WS LIVE 路径先开始 fetch，卡在旧 epoch
            ws_holding.set()
            await ws_release.wait()
            return FakeRoomInfo(LiveStatus.LIVE, live_start_time=2000), None
        # 轮询拿到关播
        return FakeRoomInfo(LiveStatus.PREPARING, live_start_time=0), None

    async def record_send(_room_id, status, *_args, **_kwargs):
        statuses.append(status)
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=record_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        ws_task = asyncio.create_task(monitor._handle_live_signal("111"))
        await ws_holding.wait()
        await monitor._check_room_status("111")
        assert state.previous_status == LiveStatus.PREPARING
        assert "end" in statuses

        ws_release.set()
        await ws_task

    assert statuses == ["end", "start"]
    assert state.previous_status == LiveStatus.LIVE


@pytest.mark.asyncio
async def test_stale_live_snapshot_from_ended_stream_is_rejected(
    live_monitor_module,
) -> None:
    """epoch 变化后，同一场次的滞后 LIVE 快照不得再触发开播。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    live_snapshot = SimpleNamespace(
        live_status=LiveStatus.LIVE,
        live_start_time=1000,
        title="title",
        cover="",
    )
    state = LiveRoomState(
        room_id=111,
        previous_status=LiveStatus.LIVE,
        start_time=1000,
        room_info=live_snapshot,
        last_live_room_info=live_snapshot,
    )
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        def __init__(self, status: LiveStatus, *, live_start_time: int):
            self.live_status = status
            self.live_start_time = live_start_time
            self.title = "title"
            self.cover = ""

        def is_living(self) -> bool:
            return self.live_status == LiveStatus.LIVE

    ws_holding = asyncio.Event()
    ws_release = asyncio.Event()
    statuses: list[str] = []
    fetch_n = 0

    async def fetch_room(*_args, **_kwargs):
        nonlocal fetch_n
        fetch_n += 1
        if fetch_n == 1:
            ws_holding.set()
            await ws_release.wait()
            # 滞后快照仍是刚结束那场的 live_start_time
            return FakeRoomInfo(LiveStatus.LIVE, live_start_time=1000), None
        return FakeRoomInfo(LiveStatus.PREPARING, live_start_time=0), None

    async def record_send(_room_id, status, *_args, **_kwargs):
        statuses.append(status)
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=record_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        ws_task = asyncio.create_task(monitor._handle_live_signal("111"))
        await ws_holding.wait()
        await monitor._check_room_status("111")
        assert state.previous_status == LiveStatus.PREPARING
        assert statuses == ["end"]

        ws_release.set()
        await ws_task

    assert statuses == ["end"]
    assert state.previous_status == LiveStatus.PREPARING


@pytest.mark.asyncio
async def test_parent_cancel_preserves_partial_start_targets(
    live_monitor_module,
) -> None:
    """父任务取消时须等投递结束，并只保留 DeliveryResult 中未成功的目标。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001", "1002"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    state = LiveRoomState(room_id=111, previous_status=LiveStatus.PREPARING)
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class FakeRoomInfo:
        live_status = LiveStatus.LIVE
        live_start_time = 1000
        title = "title"
        cover = ""

        def is_living(self) -> bool:
            return True

    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_partial(*_args, **_kwargs):
        entered.set()
        await release.wait()
        return DeliveryResult(
            targets=[
                TargetDelivery("group", "1001", True),
                TargetDelivery("group", "1002", False, "offline"),
            ]
        )

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=slow_partial),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        task = asyncio.create_task(monitor._handle_live_signal("111"))
        await entered.wait()
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert state.previous_status == LiveStatus.LIVE
    assert state.pending_start is True
    assert state.pending_start_groups == ["1002"]
    assert state.pending_start_users == []


@pytest.mark.asyncio
async def test_stale_retry_pending_serializes_with_end_flush(
    live_monitor_module,
) -> None:
    """过期轮询的 retry_pending 须等关播补发持锁结束，避免重复推送 start。"""
    from utils.bilibili_api import LiveStatus

    LiveMonitor = live_monitor_module.LiveMonitor
    LiveRoomState = sys.modules["plugins.live_monitor.models"].LiveRoomState

    config = SimpleNamespace(
        live_monitor_mapping={"111": ["1001"]},
        live_monitor_user_mapping={},
        live_at_all={},
        bilibili_cookie="",
        include_room_info=True,
        message_templates=SimpleNamespace(
            start="{streamer_name}", end="{streamer_name}"
        ),
        monitor_interval=60,
        use_websocket=True,
    )
    monitor = LiveMonitor(config)
    live_snapshot = SimpleNamespace(
        live_status=LiveStatus.LIVE,
        live_start_time=1000,
        title="title",
        cover="",
    )
    state = LiveRoomState(
        room_id=111,
        previous_status=LiveStatus.LIVE,
        start_time=1000,
        room_info=live_snapshot,
        last_live_room_info=live_snapshot,
        pending_start=True,
        pending_start_groups=["1001"],
    )
    monitor.room_states["111"] = state
    monitor.initialized_rooms["111"] = True

    class OfflineRoomInfo:
        live_status = LiveStatus.PREPARING
        live_start_time = 0
        title = "offline"
        cover = ""

        def is_living(self) -> bool:
            return False

    flush_entered = asyncio.Event()
    flush_release = asyncio.Event()
    statuses: list[str] = []

    async def slow_send(_room_id, status, *_args, **_kwargs):
        statuses.append(status)
        if status == "start" and statuses.count("start") == 1:
            flush_entered.set()
            await flush_release.wait()
        return _delivery_succeeded()

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(OfflineRoomInfo(), None),
        ),
        patch.object(monitor._delivery, "_send_notification", side_effect=slow_send),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        end_task = asyncio.create_task(
            monitor._handle_preparing_signal("111", round_status=None)
        )
        await flush_entered.wait()

        retry_task = asyncio.create_task(
            monitor._delivery.retry_pending(
                "111",
                state,
                state.last_live_room_info or live_snapshot,
                None,
            )
        )
        await asyncio.sleep(0.05)
        assert statuses == ["start"]

        flush_release.set()
        await end_task
        await retry_task

    assert statuses.count("start") == 1
    assert "end" in statuses
    assert state.pending_start is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["start", "end"])
async def test_live_sender_mixes_official_and_onebot_routes_with_card(
    status, live_sender_module, monkeypatch
):
    from nonebot.adapters.onebot.v11 import MessageSegment

    from shared.adapter import outbound
    from shared.notify.at_all import LIVE_AT_ALL_FALLBACK

    sender = live_sender_module.LiveNotificationSender()
    monkeypatch.setattr(
        sender, "_generate_card_if_needed", AsyncMock(return_value=b"card")
    )
    onebot = SimpleNamespace(send_group_msg=AsyncMock(), send_private_msg=AsyncMock())
    official = SimpleNamespace(send_to_group=AsyncMock(), send_to_c2c=AsyncMock())
    monkeypatch.setattr(
        live_sender_module, "messaging_bots", lambda: [onebot, official]
    )
    monkeypatch.setattr(outbound, "iter_onebot_bots", lambda: [onebot])
    monkeypatch.setattr(outbound, "iter_official_bots", lambda: [official])
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    prefix = AsyncMock(return_value=Message(MessageSegment.at("all")))
    monkeypatch.setattr(outbound, "resolve_at_all_prefix", prefix)
    result = await sender.send_notification(
        status,
        "author",
        None,
        ["1001", "group-openid"],
        ["2002", "user-openid"],
        at_all_enabled=True,
        duration_seconds=60,
    )
    assert result.all_succeeded
    onebot.send_group_msg.assert_awaited_once()
    onebot.send_private_msg.assert_awaited_once()
    group_calls = official.send_to_group.await_args_list
    assert [call.kwargs["message"][0].type for call in group_calls] == (
        ["text", "text", "file_image"]
        if status == "start"
        else ["text", "file_image", "text"]
    )
    if status == "start":
        assert (
            group_calls[0].kwargs["message"].extract_plain_text()
            == LIVE_AT_ALL_FALLBACK
        )
        assert onebot.send_group_msg.await_args.kwargs["message"][0].type == "at"
        prefix.assert_awaited_once()
    else:
        prefix.assert_not_awaited()
    images = [
        call.kwargs["message"][0]
        for call in official.send_to_c2c.await_args_list
        if call.kwargs["message"][0].type == "file_image"
    ]
    assert len(images) == 1 and images[0].data["content"] == b"card"


@pytest.mark.asyncio
async def test_live_permission_rejection_is_terminal(live_sender_module, monkeypatch):
    from plugins.live_monitor.models import LiveRoomState
    from plugins.live_monitor.notification_delivery import LiveNotificationDelivery
    from shared.adapter import outbound
    from shared.adapter.qq_errors import LoggedQQApiError

    sender = live_sender_module.LiveNotificationSender()
    monkeypatch.setattr(
        sender, "_generate_card_if_needed", AsyncMock(return_value=None)
    )
    bot = SimpleNamespace(
        send_to_group=AsyncMock(side_effect=LoggedQQApiError(40034105, "无权限")),
        send_to_c2c=AsyncMock(),
    )
    monkeypatch.setattr(live_sender_module, "messaging_bots", lambda: [bot])
    monkeypatch.setattr(outbound, "iter_official_bots", lambda: [bot])
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    delivery = LiveNotificationDelivery(
        sender,
        get_group_mapping=lambda: {"1": ["group-openid"]},
        get_user_mapping=lambda: {"1": ["user-openid"]},
        get_at_all=lambda: {"1": False},
    )
    state = LiveRoomState(room_id=1)
    assert await delivery.deliver_start("1", state, room_info=None, user_info=None)
    assert not state.pending_start
    bot.send_to_c2c.assert_awaited_once()
    await delivery.retry_pending("1", state, room_info=None, user_info=None)
    bot.send_to_group.assert_awaited_once()


@pytest.mark.asyncio
async def test_live_finish_write_failure_retains_acknowledged_parts(
    live_sender_module, monkeypatch
):
    from plugins.live_monitor.models import LiveRoomState
    from plugins.live_monitor.notification_delivery import LiveNotificationDelivery
    from shared.adapter import outbound

    sender = live_sender_module.LiveNotificationSender()
    monkeypatch.setattr(
        sender, "_generate_card_if_needed", AsyncMock(return_value=b"card")
    )
    bot = SimpleNamespace(send_to_group=AsyncMock())
    monkeypatch.setattr(live_sender_module, "messaging_bots", lambda: [bot])
    monkeypatch.setattr(outbound, "iter_official_bots", lambda: [bot])
    monkeypatch.setattr(outbound, "_OFFICIAL_MIN_INTERVAL", 0)
    state = LiveRoomState(room_id=1)
    fail_once = True

    async def persist(_room_id):
        nonlocal fail_once
        if not state.pending_start and fail_once:
            fail_once = False
            raise RuntimeError("write failed")

    delivery = LiveNotificationDelivery(
        sender,
        get_group_mapping=lambda: {"1": ["group-openid"]},
        get_user_mapping=lambda: {},
        get_at_all=lambda: {"1": False},
        persist_state=persist,
    )
    with pytest.raises(RuntimeError, match="write failed"):
        await delivery.deliver_start("1", state, room_info=None, user_info=None)
    assert state.pending_start
    assert state.pending_start_delivery.group_starts == {"group-openid": 2}
    assert await delivery.deliver_start("1", state, room_info=None, user_info=None)
    assert bot.send_to_group.await_count == 2
    assert not state.pending_start
