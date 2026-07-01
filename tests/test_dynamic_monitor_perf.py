"""Tests for dynamic push author-name cache and screenshot concurrency (issue #90)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.bilibili_api.dynamic_api import DynamicFetcher
from utils.bilibili_api.dynamic_models import DynamicItem

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
PLUGIN_ROOT = PLUGINS_ROOT / "dynamic_monitor"


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


def _load_module(qualified_name: str, filename: str):
    path = PLUGIN_ROOT / filename
    spec = importlib.util.spec_from_file_location(qualified_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dynamic_monitor_module():
    touched = {
        key: sys.modules.get(key)
        for key in (
            "plugins",
            "plugins.dynamic_monitor",
            "plugins.dynamic_monitor.config",
            "plugins.dynamic_monitor.sender",
            "plugins.dynamic_monitor.dynamic_monitor",
            "nonebot_plugin_apscheduler",
            "nonebot_plugin_orm",
            "utils.screenshot",
        )
    }
    screenshot_mock = MagicMock(
        init_screenshot_service=AsyncMock(),
        close_screenshot_service=AsyncMock(),
        get_dynamic_screenshot=AsyncMock(),
    )
    sys.modules["utils.screenshot"] = screenshot_mock
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.dynamic_monitor", PLUGIN_ROOT)
    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock()),
    )
    _load_module("plugins.dynamic_monitor.config", "config.py")
    _load_module("plugins.dynamic_monitor.sender", "sender.py")
    try:
        module = _load_module(
            "plugins.dynamic_monitor.dynamic_monitor", "dynamic_monitor.py"
        )
        yield module
    finally:
        for key, original in touched.items():
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


def _make_monitor(DynamicMonitor, *, enable_screenshot: bool = False):
    config = SimpleNamespace(
        dynamic_monitor_mapping={"123": ["1001"]},
        dynamic_monitor_user_mapping={},
        dynamic_at_all={},
        bilibili_cookie="",
        enable_screenshot=enable_screenshot,
    )
    monitor = DynamicMonitor(config)
    monitor.is_running = True
    monitor.initialized_uids["123"] = True
    monitor.last_dynamic_ids["123"] = 10
    monitor.pinned_dynamic_ids["123"] = None
    monitor._check_generation["123"] = 0
    monitor.fetcher = MagicMock(spec=DynamicFetcher)
    monitor.fetcher.resolve_user_name = AsyncMock(return_value="cached_name")
    monitor.sender = MagicMock()
    monitor.sender.build_dynamic_message = MagicMock(return_value="msg")
    monitor.sender.send_message = AsyncMock(
        return_value=SimpleNamespace(all_succeeded=True, targets=[])
    )
    monitor._persist_state = AsyncMock()
    return monitor


def _dynamic(
    dynamic_id: int,
    *,
    uid: int = 123,
    name: str = "feed_author",
    timestamp: int = 0,
) -> DynamicItem:
    return DynamicItem(
        dynamic_id=dynamic_id,
        uid=uid,
        name=name,
        timestamp=timestamp,
        dynamic_type=0,
    )


@pytest.mark.asyncio
async def test_feed_author_name_skips_api_for_multiple_dynamics(
    dynamic_monitor_module,
) -> None:
    """同 UID 多条新动态：feed 已有作者名时不请求用户信息 API。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor)
    monitor.fetcher = DynamicFetcher(MagicMock(), cookie="")
    monitor.fetcher._get_user_name_from_api = AsyncMock(return_value="api_name")
    dynamics = [_dynamic(11, timestamp=1), _dynamic(12, timestamp=2)]
    monitor.fetcher.fetch_user_dynamics = AsyncMock(return_value=(dynamics, None))

    ok = await monitor._check_user_dynamic("123")
    await monitor._drain_pending_deliveries()

    assert ok is True
    assert monitor.last_dynamic_ids["123"] == 12
    monitor.fetcher._get_user_name_from_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_placeholder_name_uses_api_once_for_multiple_dynamics(
    dynamic_monitor_module,
) -> None:
    """占位作者名时同 UID 多动态只触发一次 API（第二次走 TTL 缓存）。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor)
    monitor.fetcher = DynamicFetcher(MagicMock(), cookie="")
    api_calls = 0

    async def fake_api(uid: str):
        nonlocal api_calls
        api_calls += 1
        name = f"name_{uid}"
        monitor.fetcher._cache_user_name(str(uid), name)
        return name

    monitor.fetcher._get_user_name_from_api = fake_api  # type: ignore[method-assign]
    dynamics = [
        _dynamic(11, name="UP主_123", timestamp=1),
        _dynamic(12, name="UP主_123", timestamp=2),
    ]
    monitor.fetcher.fetch_user_dynamics = AsyncMock(return_value=(dynamics, None))

    ok = await monitor._check_user_dynamic("123")
    await monitor._drain_pending_deliveries()

    assert ok is True
    assert api_calls == 1
    assert monitor.last_dynamic_ids["123"] == 12


@pytest.mark.asyncio
async def test_screenshot_semaphore_limits_concurrent_capture(
    dynamic_monitor_module,
) -> None:
    """多 UID 同时推送时截图并发受 semaphore 限制。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor, enable_screenshot=True)
    monitor._screenshot_semaphore = asyncio.Semaphore(2)

    in_flight = 0
    peak = 0

    async def slow_screenshot(dynamic_id: int):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return (b"png", None, f"https://t.bilibili.com/{dynamic_id}")

    with patch.object(
        dynamic_monitor_module,
        "get_dynamic_screenshot",
        side_effect=slow_screenshot,
    ):
        results = await asyncio.gather(
            *[
                monitor._fetch_dynamic_screenshot(_dynamic(i, uid=i))
                for i in range(1, 6)
            ]
        )

    assert peak <= 2
    assert results == [b"png"] * 5


@pytest.mark.asyncio
async def test_screenshot_queue_waits_when_full(
    dynamic_monitor_module,
) -> None:
    """截图队列满时排队等待，不跳过截图。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor, enable_screenshot=True)
    monitor._screenshot_queue_semaphore = asyncio.Semaphore(2)
    monitor._screenshot_semaphore = asyncio.Semaphore(1)

    release = asyncio.Event()

    async def slow_screenshot(dynamic_id: int):
        await release.wait()
        return (b"png", None, f"https://t.bilibili.com/{dynamic_id}")

    with patch.object(
        dynamic_monitor_module,
        "get_dynamic_screenshot",
        side_effect=slow_screenshot,
    ):
        t1 = asyncio.create_task(monitor._fetch_dynamic_screenshot(_dynamic(1)))
        t2 = asyncio.create_task(monitor._fetch_dynamic_screenshot(_dynamic(2)))
        await asyncio.sleep(0.02)
        t3 = asyncio.create_task(monitor._fetch_dynamic_screenshot(_dynamic(3)))
        await asyncio.sleep(0.02)

        assert not t3.done()

        release.set()
        results = await asyncio.gather(t1, t2, t3)

    assert results == [b"png"] * 3


@pytest.mark.asyncio
async def test_screenshot_skipped_if_disabled_while_queued(
    dynamic_monitor_module,
) -> None:
    """排队等待期间热关闭截图时，不再调用 get_dynamic_screenshot。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor, enable_screenshot=True)
    monitor._screenshot_semaphore = asyncio.Semaphore(1)

    capture_started = asyncio.Event()
    release_first = asyncio.Event()
    capture_calls = 0

    async def slow_screenshot(dynamic_id: int):
        nonlocal capture_calls
        capture_calls += 1
        capture_started.set()
        await release_first.wait()
        return (b"png", None, f"https://t.bilibili.com/{dynamic_id}")

    with patch.object(
        dynamic_monitor_module,
        "get_dynamic_screenshot",
        side_effect=slow_screenshot,
    ):
        first = asyncio.create_task(monitor._fetch_dynamic_screenshot(_dynamic(1)))
        await capture_started.wait()
        second = asyncio.create_task(monitor._fetch_dynamic_screenshot(_dynamic(2)))
        await asyncio.sleep(0.02)
        monitor.config.enable_screenshot = False
        release_first.set()
        first_result, second_result = await asyncio.gather(first, second)

    assert first_result == b"png"
    assert second_result is None
    assert capture_calls == 1


@pytest.mark.asyncio
async def test_screenshot_skipped_if_stale_before_queue(
    dynamic_monitor_module,
) -> None:
    """投递已过期时不进入截图队列。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor, enable_screenshot=True)

    with patch.object(
        dynamic_monitor_module,
        "get_dynamic_screenshot",
        new_callable=AsyncMock,
    ) as screenshot_mock:
        monitor._bump_check_generation("123")
        result = await monitor._fetch_dynamic_screenshot(
            _dynamic(1), uid="123", check_generation=0
        )

    assert result is None
    screenshot_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_screenshot_skipped_if_stale_while_queued(
    dynamic_monitor_module,
) -> None:
    """排队等待期间 UID generation 变更时，不再调用 get_dynamic_screenshot。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor, enable_screenshot=True)
    monitor._screenshot_semaphore = asyncio.Semaphore(1)

    capture_started = asyncio.Event()
    release_first = asyncio.Event()
    capture_calls = 0

    async def slow_screenshot(dynamic_id: int):
        nonlocal capture_calls
        capture_calls += 1
        capture_started.set()
        await release_first.wait()
        return (b"png", None, f"https://t.bilibili.com/{dynamic_id}")

    with patch.object(
        dynamic_monitor_module,
        "get_dynamic_screenshot",
        side_effect=slow_screenshot,
    ):
        first = asyncio.create_task(
            monitor._fetch_dynamic_screenshot(
                _dynamic(1), uid="123", check_generation=0
            )
        )
        await capture_started.wait()
        second = asyncio.create_task(
            monitor._fetch_dynamic_screenshot(
                _dynamic(2), uid="123", check_generation=0
            )
        )
        await asyncio.sleep(0.02)
        monitor._bump_check_generation("123")
        release_first.set()
        first_result, second_result = await asyncio.gather(first, second)

    assert first_result == b"png"
    assert second_result is None
    assert capture_calls == 1


@pytest.mark.asyncio
async def test_build_message_uses_screenshot_when_available(
    dynamic_monitor_module,
) -> None:
    """开启截图且成功时走截图路径，不包含原图。"""
    DynamicMonitor = dynamic_monitor_module.DynamicMonitor
    monitor = _make_monitor(DynamicMonitor, enable_screenshot=True)
    monitor._fetch_dynamic_screenshot = AsyncMock(return_value=b"shot")

    delivered = await monitor._send_dynamic_notification(
        "123", _dynamic(11), check_generation=0
    )

    assert delivered is True
    _, kwargs = monitor.sender.build_dynamic_message.call_args
    assert kwargs["include_dynamic_media"] is False
