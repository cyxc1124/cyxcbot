"""Tests for group special title handler API failure paths."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import nonebot
import pytest
from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError


def _ensure_nonebot() -> None:
    os.environ["SQLALCHEMY_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=os.environ["SQLALCHEMY_DATABASE_URL"],
            alembic_startup_check=False,
        )
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("daily_limit", "failure_date"),
    [(1, "2026-07-04"), (1, "2026-07-05"), (0, "2026-07-05")],
)
async def test_set_title_network_error_releases_reserved_date(
    daily_limit: int, failure_date: str
) -> None:
    _ensure_nonebot()
    from plugins.group_special_title.handler import handle_group_special_title

    bot = MagicMock()
    bot.self_id = "100"
    bot.get_group_member_info = AsyncMock(return_value={"role": "owner"})
    current_date = "2026-07-04"

    async def fail_title(**kwargs):
        nonlocal current_date
        current_date = failure_date
        raise NetworkError("timeout")

    bot.set_group_special_title = AsyncMock(side_effect=fail_title)

    event = MagicMock()
    event.group_id = 123
    event.user_id = 456
    event.message = MagicMock()

    snap = MagicMock()
    snap.group_special_title_restrict = False
    snap.group_special_title_daily_limit = daily_limit

    with (
        patch(
            "plugins.group_special_title.handler.parse_title_from_message",
            return_value="测试",
        ),
        patch(
            "plugins.group_special_title.handler.get_config_service",
            return_value=MagicMock(get_snapshot=lambda: snap),
        ),
        patch(
            "plugins.group_special_title.handler.today_usage_date",
            side_effect=lambda: current_date,
        ) as date_mock,
        patch(
            "plugins.group_special_title.handler.try_consume_daily_quota",
            new=AsyncMock(return_value=True),
        ) as consume_mock,
        patch(
            "plugins.group_special_title.handler.release_daily_quota",
            new=AsyncMock(),
        ) as release_mock,
    ):
        await handle_group_special_title(bot, event)

    date_mock.assert_called_once_with()
    consume_mock.assert_awaited_once_with(
        "123", "456", daily_limit, usage_date="2026-07-04"
    )
    if daily_limit > 0:
        release_mock.assert_awaited_once_with("123", "456", usage_date="2026-07-04")
    else:
        release_mock.assert_not_awaited()


def test_action_failed_exposes_retcode_via_info() -> None:
    exc = ActionFailed(retcode=120, message="permission denied")
    assert exc.info.get("retcode") == 120
    assert exc.info.get("message") == "permission denied"


@pytest.mark.asyncio
async def test_role_lookup_network_error_returns_none() -> None:
    _ensure_nonebot()
    from plugins.group_special_title.handler import _bot_group_role

    bot = MagicMock()
    bot.self_id = "100"
    bot.get_group_member_info = AsyncMock(side_effect=NetworkError("timeout"))

    role = await _bot_group_role(bot, 123)

    assert role is None
