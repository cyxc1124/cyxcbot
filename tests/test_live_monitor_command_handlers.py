"""plugins/live_monitor/__init__.py 命令处理器测试（issue #150）。

覆盖点：`直播状态`/`监控列表` 必须读取模块级最新的 live_monitor_instance
（而非导入时绑定的 stale 引用），且实例未启动时的临时查询不得关闭
共享的全局 api_manager。
"""

from __future__ import annotations

import os
import sys
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import nonebot
import pytest


def _ensure_nonebot() -> None:
    os.environ.setdefault("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=os.environ["SQLALCHEMY_DATABASE_URL"],
            alembic_startup_check=False,
        )
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")
    if "nonebot_plugin_apscheduler" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_apscheduler")


_ensure_nonebot()

import plugins.live_monitor as live_monitor_plugin  # noqa: E402
from plugins.live_monitor import live_monitor as live_monitor_mod  # noqa: E402
from plugins.live_monitor.config import Config  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_live_monitor_instance():
    live_monitor_mod.live_monitor_instance = None
    yield
    live_monitor_mod.live_monitor_instance = None


def _make_event(
    group_id: int = 123, text: str = "", is_tome: bool = False
) -> MagicMock:
    event = MagicMock()
    event.group_id = group_id
    event.get_plaintext.return_value = text
    event.is_tome.return_value = is_tome
    return event


def _patch_matcher(matcher):
    return patch.multiple(matcher, send=DEFAULT, finish=DEFAULT)


@pytest.mark.asyncio
async def test_live_status_uses_instance_set_after_module_import() -> None:
    """启动后才赋值的 live_monitor_instance 必须被 直播状态 命令读取到，而非 import 时的 stale None。"""
    fake_instance = MagicMock()
    fake_instance.check_room_now = AsyncMock(
        return_value={
            "room_id": 12345,
            "streamer_name": "测试主播",
            "title": "测试标题",
            "is_living": True,
            "live_status": "LIVE",
            "area": "分区A - 分区B",
            "online": 100,
        }
    )
    # 模拟 start_live_monitor() 在运行期赋值模块属性（而不是通过 __init__.py 里绑定的旧引用）
    live_monitor_mod.live_monitor_instance = fake_instance

    event = _make_event(text="直播状态 12345")

    with _patch_matcher(live_monitor_plugin.live_status_cmd) as mocks:
        await live_monitor_plugin.handle_live_status(MagicMock(), event)

    fake_instance.check_room_now.assert_awaited_once_with("12345")
    mocks["finish"].assert_awaited_once()
    assert "测试主播" in str(mocks["finish"].await_args.args[0])


@pytest.mark.asyncio
async def test_live_status_without_instance_does_not_close_shared_api_manager() -> None:
    """实例未启动时的临时查询必须使用独立 session，不能调用共享 api_manager.close()。"""
    live_monitor_mod.live_monitor_instance = None

    fake_room_info = MagicMock()
    fake_room_info.room_id = 12345
    fake_room_info.title = "测试标题"
    fake_room_info.is_living.return_value = False
    fake_room_info.live_status.name = "PREPARING"
    fake_room_info.parent_area_name = "分区A"
    fake_room_info.area_name = "分区B"
    fake_room_info.online = 0

    event = _make_event(text="直播状态 12345")

    with (
        patch(
            "plugins.live_monitor.Config.from_service",
            return_value=Config(bilibili_cookie=None),
        ),
        patch(
            "utils.bilibili_api.live_api.LiveApi.get_room_and_user_info",
            new=AsyncMock(return_value=(fake_room_info, None)),
        ),
        patch(
            "utils.bilibili_api.api_manager.init", new_callable=AsyncMock
        ) as shared_init,
        patch(
            "utils.bilibili_api.api_manager.close", new_callable=AsyncMock
        ) as shared_close,
        _patch_matcher(live_monitor_plugin.live_status_cmd) as mocks,
    ):
        await live_monitor_plugin.handle_live_status(MagicMock(), event)

    shared_init.assert_not_awaited()
    shared_close.assert_not_awaited()
    mocks["finish"].assert_awaited_once()
    assert "房间12345" in str(mocks["finish"].await_args.args[0])


@pytest.mark.asyncio
async def test_list_monitor_uses_instance_set_after_module_import() -> None:
    """`监控列表` 命令必须能读取到运行中实例的最新 room_states。"""
    fake_state = MagicMock()
    fake_state.user_info.name = "测试主播"
    fake_state.room_info.is_living.return_value = True

    fake_instance = MagicMock()
    fake_instance.room_states = {"12345": fake_state}
    live_monitor_mod.live_monitor_instance = fake_instance

    fake_config = Config(live_monitor_mapping={"12345": ["123"]})

    with (
        patch("plugins.live_monitor.Config.from_service", return_value=fake_config),
        _patch_matcher(live_monitor_plugin.list_monitor_cmd) as mocks,
    ):
        await live_monitor_plugin.handle_list_monitor(
            MagicMock(), _make_event(text="监控列表")
        )

    mocks["finish"].assert_awaited_once()
    message = str(mocks["finish"].await_args.args[0])
    assert "测试主播" in message
    assert "🔴" in message


@pytest.mark.asyncio
async def test_list_monitor_without_instance_falls_back_to_offline() -> None:
    """无运行中实例时，监控列表应展示离线占位而不是报错。"""
    live_monitor_mod.live_monitor_instance = None
    fake_config = Config(live_monitor_mapping={"12345": ["123"]})

    with (
        patch("plugins.live_monitor.Config.from_service", return_value=fake_config),
        _patch_matcher(live_monitor_plugin.list_monitor_cmd) as mocks,
    ):
        await live_monitor_plugin.handle_list_monitor(
            MagicMock(), _make_event(text="监控列表")
        )

    message = str(mocks["finish"].await_args.args[0])
    assert "房间12345" in message
    assert "⚫" in message
