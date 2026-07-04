"""Tests for group special title handler API failure paths."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import nonebot
import pytest
from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError


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


@pytest.mark.asyncio
async def test_set_title_network_error_releases_quota() -> None:
    _ensure_nonebot()
    from plugins.group_special_title.handler import handle_group_special_title

    bot = MagicMock()
    bot.self_id = "100"
    bot.get_group_member_info = AsyncMock(return_value={"role": "owner"})
    bot.set_group_special_title = AsyncMock(side_effect=NetworkError("timeout"))

    event = MagicMock()
    event.group_id = 123
    event.user_id = 456
    event.message = MagicMock()

    snap = MagicMock()
    snap.group_special_title_restrict = False
    snap.group_special_title_daily_limit = 1

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
            "plugins.group_special_title.handler.try_consume_daily_quota",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "plugins.group_special_title.handler.release_daily_quota",
            new=AsyncMock(),
        ) as release_mock,
    ):
        await handle_group_special_title(bot, event)

    release_mock.assert_awaited_once_with("123", "456")


def test_action_failed_exposes_retcode_via_info() -> None:
    exc = ActionFailed(retcode=120, message="permission denied")
    assert exc.info.get("retcode") == 120
    assert exc.info.get("message") == "permission denied"
