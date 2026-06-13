"""Tests for dynamic monitor config hot reload."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
PLUGIN_ROOT = PLUGINS_ROOT / "dynamic_monitor"

_TOUCHED_MODULE_KEYS = (
    "plugins",
    "plugins.dynamic_monitor",
    "plugins.dynamic_monitor.config",
    "plugins.dynamic_monitor.dynamic_monitor",
    "plugins.dynamic_monitor.sender",
    "nonebot_plugin_apscheduler",
    "nonebot_plugin_orm",
    "utils.screenshot",
)


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
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _import_dynamic_monitor_modules():
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
    sys.modules.setdefault(
        "plugins.dynamic_monitor.sender",
        MagicMock(DynamicSender=MagicMock()),
    )
    sys.modules.setdefault(
        "utils.screenshot",
        MagicMock(
            init_screenshot_service=AsyncMock(),
            close_screenshot_service=AsyncMock(),
            get_dynamic_screenshot=AsyncMock(),
        ),
    )

    config_mod = _load_module("plugins.dynamic_monitor.config", "config.py")
    monitor_mod = _load_module(
        "plugins.dynamic_monitor.dynamic_monitor", "dynamic_monitor.py"
    )
    return config_mod.Config, monitor_mod.DynamicMonitor


@pytest.fixture
def dynamic_monitor_modules() -> Iterator[tuple[Any, Any]]:
    snapshot = {key: sys.modules.get(key) for key in _TOUCHED_MODULE_KEYS}
    try:
        yield _import_dynamic_monitor_modules()
    finally:
        for key in _TOUCHED_MODULE_KEYS:
            original = snapshot[key]
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


def _make_monitor(
    Config: Any,
    DynamicMonitor: Any,
    uids: list[str],
):
    config = Config(
        dynamic_monitor_mapping={uid: ["group1"] for uid in uids},
    )
    monitor = DynamicMonitor(config)
    monitor.is_running = True
    for uid in uids:
        monitor.last_dynamic_ids[uid] = 100
        monitor.initialized_uids[uid] = True
        monitor.pinned_dynamic_ids[uid] = 42
    return monitor


@pytest.mark.asyncio
async def test_stale_check_skips_notification_after_disable_reenable_bumps_generation(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    """停用并重启用会递增 check generation，过期 fetch 不得误推送或写回状态。"""
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111"])
    monitor.fetcher = MagicMock()
    monitor.last_dynamic_ids["111"] = 100

    fetch_started = asyncio.Event()
    release_fetch = asyncio.Event()

    async def slow_fetch(*_args, **_kwargs):
        fetch_started.set()
        await release_fetch.wait()
        return ([_dynamic(200), _dynamic(300)], None)

    monitor.fetcher.fetch_user_dynamics = slow_fetch

    with (
        patch.object(monitor, "_send_dynamic_notification", AsyncMock()) as notify,
        patch.object(monitor, "_persist_state", AsyncMock()) as persist,
    ):
        stale_task = asyncio.create_task(monitor._check_user_dynamic("111"))
        await fetch_started.wait()

        monitor._remove_uid("111")
        monitor.config = Config(dynamic_monitor_mapping={"111": ["group1"]})
        monitor._bump_check_generation("111")
        monitor.last_dynamic_ids["111"] = 100
        monitor.initialized_uids["111"] = True

        release_fetch.set()
        await stale_task

    notify.assert_not_awaited()
    persist.assert_not_awaited()
    assert monitor.last_dynamic_ids["111"] == 100


@pytest.mark.asyncio
async def test_reload_config_removes_deleted_uid_runtime_state(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111", "222"])

    reduced_config = Config(
        dynamic_monitor_mapping={"222": ["group1"]},
    )

    with (
        patch(
            "plugins.dynamic_monitor.dynamic_monitor.Config.from_service",
            return_value=reduced_config,
        ),
        patch.object(
            monitor,
            "_delete_persisted_state",
            new_callable=AsyncMock,
        ),
    ):
        await monitor.reload_config()

    assert "111" not in monitor.last_dynamic_ids
    assert "111" not in monitor.initialized_uids
    assert "111" not in monitor.pinned_dynamic_ids
    assert "222" in monitor.last_dynamic_ids


@pytest.mark.asyncio
async def test_reenabled_uid_treated_as_new_after_reload_removal(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111"])

    disabled_config = Config(dynamic_monitor_mapping={})
    reenabled_config = Config(dynamic_monitor_mapping={"111": ["group1"]})

    with (
        patch(
            "plugins.dynamic_monitor.dynamic_monitor.Config.from_service",
            side_effect=[disabled_config, reenabled_config],
        ),
        patch.object(
            monitor,
            "_delete_persisted_state",
            new_callable=AsyncMock,
        ),
    ):
        await monitor.reload_config()
        await monitor.reload_config()

    assert monitor.last_dynamic_ids["111"] == 0
    assert monitor.initialized_uids["111"] is False
    assert monitor.pinned_dynamic_ids["111"] is None


@pytest.mark.asyncio
async def test_persist_state_skips_inactive_uid(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111"])
    monitor.config = Config(dynamic_monitor_mapping={})
    monitor.last_dynamic_ids["111"] = 999
    monitor.initialized_uids["111"] = True

    with patch("plugins.dynamic_monitor.dynamic_monitor.get_session") as get_session:
        await monitor._persist_state("111")

    get_session.assert_not_called()


@pytest.mark.asyncio
async def test_check_user_dynamic_does_not_persist_after_target_removed_during_fetch(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111"])
    monitor.fetcher = MagicMock()

    async def fetch_after_disable(*_args, **_kwargs):
        monitor.config = Config(dynamic_monitor_mapping={})
        return ([], None)

    monitor.fetcher.fetch_user_dynamics = fetch_after_disable

    with patch.object(monitor, "_persist_state", AsyncMock()) as persist:
        result = await monitor._check_user_dynamic("111")

    assert result is True
    persist.assert_not_awaited()


def _dynamic(dynamic_id: int, timestamp: int = 0) -> SimpleNamespace:
    return SimpleNamespace(id=dynamic_id, timestamp=timestamp)


async def _run_stale_check_during_disable_reenable_via_reload_config(
    monitor: Any,
    Config: Any,
) -> tuple[AsyncMock, AsyncMock]:
    """在 fetch 进行中通过 reload_config 模拟停用→重启用，等待过期检查完成。"""
    disabled_config = Config(dynamic_monitor_mapping={})
    reenabled_config = Config(dynamic_monitor_mapping={"111": ["group1"]})

    fetch_started = asyncio.Event()
    release_fetch = asyncio.Event()
    fetch_calls = 0

    async def slow_then_empty_fetch(*_args, **_kwargs):
        nonlocal fetch_calls
        fetch_calls += 1
        if fetch_calls == 1:
            fetch_started.set()
            await release_fetch.wait()
            return ([_dynamic(200), _dynamic(300)], None)
        return ([], None)

    monitor.fetcher.fetch_user_dynamics = slow_then_empty_fetch

    with (
        patch(
            "plugins.dynamic_monitor.dynamic_monitor.Config.from_service",
            side_effect=[disabled_config, reenabled_config],
        ),
        patch.object(
            monitor,
            "_delete_persisted_state",
            new_callable=AsyncMock,
        ),
        patch.object(monitor, "_send_dynamic_notification", AsyncMock()) as notify,
        patch.object(monitor, "_persist_state", AsyncMock()) as persist,
    ):
        stale_task = asyncio.create_task(monitor._check_user_dynamic("111"))
        await fetch_started.wait()

        await monitor.reload_config()
        await monitor.reload_config()

        release_fetch.set()
        await stale_task

    return notify, persist


@pytest.mark.asyncio
async def test_stale_check_skips_notification_after_disable_reenable_via_reload_config(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    """reload_config 停用→重启用会递增 generation，过期 fetch 不得误推送或写回状态。"""
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111"])
    monitor.fetcher = MagicMock()
    monitor.last_dynamic_ids["111"] = 100

    notify, persist = await _run_stale_check_during_disable_reenable_via_reload_config(
        monitor,
        Config,
    )

    notify.assert_not_awaited()
    persist.assert_awaited_once_with("111")
    assert monitor.last_dynamic_ids["111"] == 0
    assert monitor.initialized_uids["111"] is True
    assert monitor.pinned_dynamic_ids["111"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initialized", "last_dynamic_id", "dynamics"),
    [
        (False, 0, [_dynamic(999)]),
        (True, 100, [_dynamic(200)]),
    ],
)
async def test_check_user_dynamic_does_not_mutate_runtime_state_after_target_removed_during_fetch(
    dynamic_monitor_modules: tuple[Any, Any],
    initialized: bool,
    last_dynamic_id: int,
    dynamics: list[SimpleNamespace],
) -> None:
    """fetch 期间目标被停用后，不应写回运行时内存状态。"""
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111"])
    monitor.fetcher = MagicMock()
    monitor.last_dynamic_ids["111"] = last_dynamic_id
    monitor.initialized_uids["111"] = initialized
    monitor.pinned_dynamic_ids["111"] = 42

    async def fetch_after_disable(*_args, **_kwargs):
        monitor.config = Config(dynamic_monitor_mapping={})
        return (dynamics, 999 if initialized else None)

    monitor.fetcher.fetch_user_dynamics = fetch_after_disable

    with patch.object(monitor, "_persist_state", AsyncMock()) as persist:
        result = await monitor._check_user_dynamic("111")

    assert result is True
    assert monitor.last_dynamic_ids["111"] == last_dynamic_id
    assert monitor.initialized_uids["111"] is initialized
    assert monitor.pinned_dynamic_ids["111"] == 42
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_reenabled_uid_reset_after_stale_inflight_check_repollutes_memory(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    """停用后进行中的检查可能把旧基准写回内存，重新启用时必须强制重置。"""
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111"])

    disabled_config = Config(dynamic_monitor_mapping={})
    reenabled_config = Config(dynamic_monitor_mapping={"111": ["group1"]})

    with (
        patch(
            "plugins.dynamic_monitor.dynamic_monitor.Config.from_service",
            return_value=disabled_config,
        ),
        patch.object(
            monitor,
            "_delete_persisted_state",
            new_callable=AsyncMock,
        ),
    ):
        await monitor.reload_config()

    # 模拟停用后过期检查把 initialized=true 的旧基准写回内存（DB 已被拦截）
    monitor.last_dynamic_ids["111"] = 100
    monitor.initialized_uids["111"] = True

    with (
        patch(
            "plugins.dynamic_monitor.dynamic_monitor.Config.from_service",
            return_value=reenabled_config,
        ),
        patch.object(
            monitor,
            "_delete_persisted_state",
            new_callable=AsyncMock,
        ) as delete_state,
        patch.object(
            monitor,
            "_check_user_dynamic",
            new_callable=AsyncMock,
        ) as check_user,
    ):
        await monitor.reload_config()

    assert monitor.last_dynamic_ids["111"] == 0
    assert monitor.initialized_uids["111"] is False
    assert monitor.pinned_dynamic_ids["111"] is None
    delete_state.assert_awaited_once_with("111")
    check_user.assert_awaited_once_with("111")


@pytest.mark.asyncio
async def test_reload_config_deletes_persisted_state_for_removed_uid(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    Config, DynamicMonitor = dynamic_monitor_modules
    monitor = _make_monitor(Config, DynamicMonitor, ["111", "222"])

    reduced_config = Config(
        dynamic_monitor_mapping={"222": ["group1"]},
    )

    with (
        patch(
            "plugins.dynamic_monitor.dynamic_monitor.Config.from_service",
            return_value=reduced_config,
        ),
        patch.object(
            monitor,
            "_delete_persisted_state",
            new_callable=AsyncMock,
        ) as delete_state,
    ):
        await monitor.reload_config()

    delete_state.assert_awaited_once_with("111")


@pytest.mark.asyncio
async def test_start_dynamic_monitor_registers_config_reload_once(
    dynamic_monitor_modules: tuple[Any, Any],
) -> None:
    _Config, _DynamicMonitor = dynamic_monitor_modules
    monitor_mod = sys.modules["plugins.dynamic_monitor.dynamic_monitor"]
    monitor_mod._config_reload_registered = False
    monitor_mod.dynamic_monitor_instance = None

    config = _Config(dynamic_monitor_mapping={"111": ["group1"]})
    fake_monitor = AsyncMock()
    fake_monitor.start_monitoring = AsyncMock()

    with (
        patch.object(monitor_mod, "Config") as config_cls,
        patch.object(monitor_mod, "DynamicMonitor", return_value=fake_monitor),
        patch.object(
            monitor_mod.get_config_service(),
            "register_reload_callback",
        ) as register,
    ):
        config_cls.from_service.return_value = config
        await monitor_mod.start_dynamic_monitor()
        await monitor_mod.stop_dynamic_monitor()
        await monitor_mod.start_dynamic_monitor()

    assert register.call_count == 1
    monitor_mod._config_reload_registered = False
    monitor_mod.dynamic_monitor_instance = None
