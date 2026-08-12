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
def dynamic_monitor_module():
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
    return _load_module(
        "plugins.dynamic_monitor.dynamic_monitor",
        DYNAMIC_MONITOR_ROOT,
        "dynamic_monitor.py",
    )


@pytest.fixture
def live_monitor_module():
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
    return _load_module(
        "plugins.live_monitor.live_monitor",
        LIVE_MONITOR_ROOT,
        "live_monitor.py",
    )


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
    with patch("plugins.dynamic_monitor.sender.get_driver", return_value=driver):
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

    with patch("plugins.dynamic_monitor.sender.get_driver", return_value=driver):
        result = await sender.send_message(Message("hi"), ["1001"], ["2002"])

    assert result.all_succeeded
    bot.send_group_msg.assert_awaited_once()
    bot.send_private_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_dynamic_sender_partial_failure(dynamic_sender_module) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = dynamic_sender_module.DynamicSender()
    bot = MagicMock(spec=Bot)
    bot.send_group_msg = AsyncMock(side_effect=RuntimeError("send failed"))
    bot.send_private_msg = AsyncMock()
    driver = SimpleNamespace(bots={"bot": bot})

    with patch("plugins.dynamic_monitor.sender.get_driver", return_value=driver):
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

    with patch("plugins.dynamic_monitor.sender.get_driver", return_value=driver):
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

    with patch("plugins.dynamic_monitor.sender.get_driver", return_value=driver):
        result = await sender.send_to_groups(Message("hi"), ["1001"])

    assert result.all_succeeded
    first_bot.send_group_msg.assert_awaited_once()
    second_bot.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_sender_no_bot_marks_targets_failed(live_sender_module) -> None:
    sender = live_sender_module.LiveNotificationSender()
    driver = SimpleNamespace(bots={})

    with patch("plugins.live_monitor.sender.get_driver", return_value=driver):
        result = await sender.send_notification(
            status="start",
            streamer_name="tester",
            room_info=None,
            target_groups=["1001"],
            target_users=["2002"],
        )

    assert result.all_failed
    assert len(result.targets) == 2


@pytest.mark.asyncio
async def test_live_sender_partial_failure(live_sender_module) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = live_sender_module.LiveNotificationSender()
    bot = MagicMock(spec=Bot)
    bot.send_group_msg = AsyncMock(side_effect=RuntimeError("group failed"))
    bot.send_private_msg = AsyncMock()
    driver = SimpleNamespace(bots={"bot": bot})

    with (
        patch("plugins.live_monitor.sender.get_driver", return_value=driver),
        patch.object(sender, "_generate_card_if_needed", AsyncMock(return_value=None)),
        patch.object(
            sender,
            "_resolve_at_all_map",
            AsyncMock(return_value={"1001": False}),
        ),
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
        patch("plugins.live_monitor.sender.get_driver", return_value=driver),
        patch.object(sender, "_generate_card_if_needed", AsyncMock(return_value=None)),
        patch.object(
            sender,
            "_resolve_at_all_map",
            AsyncMock(return_value={"1001": False}),
        ),
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
        patch("plugins.live_monitor.sender.get_driver", return_value=driver),
        patch.object(sender, "_generate_card_if_needed", AsyncMock(return_value=None)),
        patch.object(
            sender,
            "_resolve_at_all_map",
            AsyncMock(return_value={"1001": False}),
        ),
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
    monitor._persist_state.assert_not_awaited()


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
    monitor._persist_state.assert_awaited_once()


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

        await monitor._check_room_status("111")
        release_send.set()
        await ws_task

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

        await monitor._check_room_status("111")
        release_send.set()
        await ws_task

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
        assert state.pending_start is False

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
