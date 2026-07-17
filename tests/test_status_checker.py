"""plugins/status_check/status_checker.py 格式化逻辑测试（issue #142）。

覆盖点：status_checker 不再自行探测容器/cgroup 信息，而是消费
shared.monitor.system_metrics 提供的公共 helper；这里通过 monkeypatch
这些 helper 来验证格式化输出是否正确响应容器/宿主机等场景。
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import DEFAULT, MagicMock, patch

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


_ensure_nonebot()

from nonebot.adapters.onebot.v11 import (  # noqa: E402
    GroupMessageEvent,
    PrivateMessageEvent,
)

from plugins.status_check import status_checker  # noqa: E402


def test_format_uptime_various_durations():
    assert status_checker.format_uptime(30) == "30秒"
    assert status_checker.format_uptime(90) == "1分钟30秒"
    assert status_checker.format_uptime(3661) == "1小时1分钟"
    assert status_checker.format_uptime(90000) == "1天1小时0分钟"


def test_get_system_info_reports_kubernetes(monkeypatch):
    monkeypatch.setattr(
        status_checker,
        "detect_container_environment",
        lambda: {"is_container": True, "is_docker": False, "is_kubernetes": True},
    )
    assert "[Kubernetes Pod]" in status_checker.get_system_info()


def test_get_system_info_reports_docker(monkeypatch):
    monkeypatch.setattr(
        status_checker,
        "detect_container_environment",
        lambda: {"is_container": True, "is_docker": True, "is_kubernetes": False},
    )
    assert "[Docker Container]" in status_checker.get_system_info()


def test_get_system_info_bare_metal_has_no_container_tag(monkeypatch):
    monkeypatch.setattr(
        status_checker,
        "detect_container_environment",
        lambda: {"is_container": False, "is_docker": False, "is_kubernetes": False},
    )
    assert "[" not in status_checker.get_system_info()


def test_get_detailed_memory_info_prefers_container_snapshot(monkeypatch):
    monkeypatch.setattr(
        status_checker,
        "detect_container_environment",
        lambda: {"is_container": True, "is_docker": True, "is_kubernetes": False},
    )
    monkeypatch.setattr(
        status_checker,
        "get_container_memory_info",
        lambda: {
            "used_gb": 1.0,
            "total_gb": 2.0,
            "available_gb": 1.0,
            "percent": 50.0,
        },
    )
    info = status_checker.get_detailed_memory_info()
    assert "1.0GB/2.0GB" in info
    assert "[容器]" in info


def test_get_detailed_memory_info_falls_back_to_host_memory(monkeypatch):
    monkeypatch.setattr(
        status_checker,
        "detect_container_environment",
        lambda: {"is_container": True, "is_docker": True, "is_kubernetes": False},
    )
    monkeypatch.setattr(status_checker, "get_container_memory_info", lambda: None)
    info = status_checker.get_detailed_memory_info()
    assert "宿主机，Pod未设置内存限制" in info


def _fake_snapshot(cpu_percent: float = 12.3, cpu_count: int = 4) -> SimpleNamespace:
    return SimpleNamespace(cpu_percent=cpu_percent, cpu_count=cpu_count)


def test_get_cpu_info_reports_container_limit(monkeypatch):
    monkeypatch.setattr(status_checker, "get_cached_snapshot", lambda: _fake_snapshot())
    monkeypatch.setattr(status_checker.psutil, "cpu_freq", lambda: None)
    monkeypatch.setattr(
        status_checker,
        "detect_container_environment",
        lambda: {"is_container": True, "is_docker": True, "is_kubernetes": False},
    )
    monkeypatch.setattr(status_checker, "get_container_cpu_limit", lambda: 1.5)
    info = status_checker.get_cpu_info()
    assert "限制1.5核" in info
    assert "[容器]" in info


def test_get_cpu_info_host_without_limit(monkeypatch):
    monkeypatch.setattr(status_checker, "get_cached_snapshot", lambda: _fake_snapshot())
    monkeypatch.setattr(status_checker.psutil, "cpu_freq", lambda: None)
    monkeypatch.setattr(
        status_checker,
        "detect_container_environment",
        lambda: {"is_container": False, "is_docker": False, "is_kubernetes": False},
    )
    info = status_checker.get_cpu_info()
    assert "4核" in info
    assert "[容器]" not in info


@pytest.mark.asyncio
async def test_check_status_permission_allows_superuser(monkeypatch):
    async def fake_superuser(bot, event):
        return True

    monkeypatch.setattr(status_checker, "SUPERUSER", fake_superuser)

    class FakeEvent:
        user_id = 12345

    assert await status_checker.check_status_permission(None, FakeEvent()) is True


@pytest.mark.asyncio
async def test_handle_status_command_private_message_requires_exact_trigger(
    monkeypatch,
):
    """回归测试：PrivateMessageEvent.is_tome() 恒为 True，若直接传给
    match_plain 会走 @机器人 模糊匹配分支，导致好友随口一句"状态怎么样"/
    "请看运行状态"也触发完整状态播报（迁移自 on_command 前只有逐字精确输入
    触发词才会响应）。私聊应强制精确匹配，仅群聊被 @/回复时才走模糊匹配。
    """

    async def fake_permission(bot, event):
        return True

    monkeypatch.setattr(status_checker, "check_status_permission", fake_permission)

    private_event = MagicMock(spec=PrivateMessageEvent)
    private_event.is_tome.return_value = True

    private_event.get_plaintext.return_value = "状态怎么样"
    with patch.multiple(
        status_checker.status_cmd, send=DEFAULT, finish=DEFAULT
    ) as mocks:
        await status_checker.handle_status_command(MagicMock(), private_event)
    mocks["finish"].assert_not_awaited()

    # 私聊里完整发送触发词仍应正常响应
    private_event.get_plaintext.return_value = "运行状态"
    with patch.multiple(
        status_checker.status_cmd, send=DEFAULT, finish=DEFAULT
    ) as mocks:
        await status_checker.handle_status_command(MagicMock(), private_event)
    mocks["finish"].assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_status_command_group_at_bot_keeps_fuzzy_match(monkeypatch):
    """群聊里被 @/回复时应保留模糊匹配（迁移前 dynamic_monitor 等插件的既有约定）。"""

    async def fake_permission(bot, event):
        return True

    monkeypatch.setattr(status_checker, "check_status_permission", fake_permission)

    group_event = MagicMock(spec=GroupMessageEvent)
    group_event.is_tome.return_value = True
    group_event.get_plaintext.return_value = "状态怎么样"

    with patch.multiple(
        status_checker.status_cmd, send=DEFAULT, finish=DEFAULT
    ) as mocks:
        await status_checker.handle_status_command(MagicMock(), group_event)
    mocks["finish"].assert_awaited_once()
