"""Tests for monitor notification delivery results and retry behavior."""

from __future__ import annotations

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
    with patch("nonebot.get_bot", side_effect=RuntimeError("no bot")):
        result = await sender.send_message(Message("hi"), ["1001"], ["2002"])

    assert result.attempted
    assert result.all_failed
    assert len(result.targets) == 2
    assert all(not target.success for target in result.targets)


@pytest.mark.asyncio
async def test_dynamic_sender_all_targets_succeed(dynamic_sender_module) -> None:
    sender = dynamic_sender_module.DynamicSender()
    bot = AsyncMock()
    bot.send_group_msg = AsyncMock()
    bot.send_private_msg = AsyncMock()

    with patch("nonebot.get_bot", return_value=bot):
        result = await sender.send_message(Message("hi"), ["1001"], ["2002"])

    assert result.all_succeeded
    bot.send_group_msg.assert_awaited_once()
    bot.send_private_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_dynamic_sender_partial_failure(dynamic_sender_module) -> None:
    sender = dynamic_sender_module.DynamicSender()
    bot = AsyncMock()
    bot.send_group_msg = AsyncMock(side_effect=RuntimeError("send failed"))
    bot.send_private_msg = AsyncMock()

    with patch("nonebot.get_bot", return_value=bot):
        result = await sender.send_message(Message("hi"), ["1001"], ["2002"])

    assert result.any_succeeded
    assert not result.all_succeeded
    assert result.targets[0].success is False
    assert result.targets[1].success is True


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
async def test_live_sender_aggregates_multi_bot_delivery_by_target(
    live_sender_module,
) -> None:
    from nonebot.adapters.onebot.v11 import Bot

    sender = live_sender_module.LiveNotificationSender()
    bot_ok = MagicMock(spec=Bot)
    bot_ok.send_group_msg = AsyncMock()
    bot_ok.send_private_msg = AsyncMock()
    bot_fail = MagicMock(spec=Bot)
    bot_fail.send_group_msg = AsyncMock(side_effect=RuntimeError("no access"))
    bot_fail.send_private_msg = AsyncMock(side_effect=RuntimeError("no access"))
    driver = SimpleNamespace(bots={"ok": bot_ok, "fail": bot_fail})

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
    bot_ok.send_group_msg.assert_awaited_once()
    bot_fail.send_group_msg.assert_awaited_once()


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
    monitor.fetcher._get_user_name_from_api = AsyncMock(return_value="tester")
    monitor.fetcher.fetch_user_dynamics = AsyncMock(return_value=([dynamic], None))
    monitor._persist_state = AsyncMock()

    ok = await monitor._check_user_dynamic("123")

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
    monitor.fetcher._get_user_name_from_api = AsyncMock(return_value="tester")
    monitor.fetcher.fetch_user_dynamics = AsyncMock(return_value=([dynamic], None))
    monitor._persist_state = AsyncMock()

    ok = await monitor._check_user_dynamic("123")

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

    send_mock = AsyncMock(side_effect=[False, True])

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            side_effect=fetch_room,
        ),
        patch.object(monitor, "_send_live_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._check_room_status("111")
        await monitor._check_room_status("111")

    assert state.previous_status == LiveStatus.PREPARING
    assert state.pending_start is False
    assert state.pending_end is False
    assert send_mock.await_args_list[0].args[1] == "start"
    assert send_mock.await_args_list[1].args[1] == "end"


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

    send_mock = AsyncMock(side_effect=[False, True])

    with (
        patch(
            "plugins.live_monitor.live_monitor.api_manager.get_room_and_user_info",
            return_value=(FakeRoomInfo(), None),
        ),
        patch.object(monitor, "_send_live_notification", send_mock),
        patch.object(monitor, "_persist_state", AsyncMock()),
    ):
        await monitor._check_room_status("111")
        await monitor._check_room_status("111")

    assert state.previous_status == LiveStatus.LIVE
    assert state.pending_start is False
    assert send_mock.await_count == 2
    assert all(call.args[1] == "start" for call in send_mock.await_args_list)
