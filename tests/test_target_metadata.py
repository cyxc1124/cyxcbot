"""Tests for admin target name resolution (issue #89)."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import nonebot
import pytest

os.environ.setdefault("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
try:
    nonebot.get_driver()
except ValueError:
    nonebot.init(
        sqlalchemy_database_url=os.environ["SQLALCHEMY_DATABASE_URL"],
        alembic_startup_check=False,
    )
    nonebot.load_plugin("nonebot_plugin_orm")

from admin.services import target_metadata as tm


@pytest.mark.asyncio
async def test_resolve_dynamic_target_name_skips_bilibili_when_manual():
    with patch.object(tm, "resolve_up_name", new_callable=AsyncMock) as mock_resolve:
        result = await tm.resolve_dynamic_target_name("12345", "手动名称")
    assert result == "手动名称"
    mock_resolve.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_live_target_name_skips_bilibili_when_manual():
    with patch.object(
        tm, "resolve_live_streamer_name", new_callable=AsyncMock
    ) as mock_resolve:
        result = await tm.resolve_live_target_name("123", "主播名")
    assert result == "主播名"
    mock_resolve.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_dynamic_target_name_fetches_when_no_manual():
    with patch.object(
        tm, "resolve_up_name", new_callable=AsyncMock, return_value="B站昵称"
    ) as mock_resolve:
        result = await tm.resolve_dynamic_target_name("12345", None)
    assert result == "B站昵称"
    mock_resolve.assert_awaited_once_with("12345")


@pytest.mark.asyncio
async def test_resolve_up_name_reuses_passed_session():
    session = MagicMock()
    with patch.object(
        tm, "_resolve_up_name_with_session", new_callable=AsyncMock, return_value="昵称"
    ) as mock_inner:
        result = await tm.resolve_up_name("99", session=session)
    assert result == "昵称"
    mock_inner.assert_awaited_once_with(session, "99")


@pytest.mark.asyncio
async def test_batch_resolve_missing_dynamic_names_uses_single_session():
    calls: list[str] = []

    async def fake_resolve(session, uid: str) -> str | None:
        calls.append(uid)
        assert session is shared_session
        return f"name-{uid}"

    shared_session = MagicMock()
    mock_db_session = MagicMock()
    mock_db_session.begin = MagicMock(return_value=AsyncMock())
    mock_db_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_db_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)

    target_a = MagicMock()
    target_a.name = None
    target_b = MagicMock()
    target_b.name = None

    async def fake_get(_model, target_id: int):
        return {1: target_a, 2: target_b}.get(target_id)

    mock_db_session.get = AsyncMock(side_effect=fake_get)

    with (
        patch.object(
            tm.aiohttp,
            "ClientSession",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=shared_session),
                __aexit__=AsyncMock(return_value=None),
            ),
        ),
        patch.object(tm, "_resolve_up_name_with_session", side_effect=fake_resolve),
        patch(
            "nonebot_plugin_orm.get_session",
            return_value=mock_db_session,
        ),
    ):
        await tm.resolve_missing_dynamic_target_names([(1, "111"), (2, "222")])

    assert calls == ["111", "222"]
    assert target_a.name == "name-111"
    assert target_b.name == "name-222"


@pytest.mark.asyncio
async def test_list_endpoint_does_not_block_on_slow_bilibili(monkeypatch):
    """List handler returns before background name refresh completes."""
    import admin.api.v1.targets as targets_api

    slow_started = asyncio.Event()
    slow_release = asyncio.Event()

    async def slow_refresh(_items: list[tuple[int, str]]) -> None:
        slow_started.set()
        await slow_release.wait()

    target = MagicMock()
    target.id = 1
    target.uid = "123"
    target.name = None
    target.groups = []
    target.users = []
    target.enabled = True
    target.at_all = False
    target.created_at = target.updated_at = MagicMock()

    mock_session = MagicMock()
    mock_session.begin = MagicMock(return_value=AsyncMock())
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_session.scalars = AsyncMock(
        return_value=MagicMock(all=MagicMock(return_value=[target]))
    )

    spawned: list[asyncio.Task] = []

    def capture_spawn(name, coro, **kwargs):
        task = asyncio.create_task(coro)
        spawned.append(task)
        return task

    monkeypatch.setattr(targets_api, "get_session", lambda: mock_session)
    monkeypatch.setattr(
        targets_api, "resolve_missing_dynamic_target_names", slow_refresh
    )
    monkeypatch.setattr(targets_api, "spawn_background_task", capture_spawn)

    result = await asyncio.wait_for(targets_api.list_dynamic_targets(MagicMock()), 0.1)

    assert len(result) == 1
    assert result[0].name is None
    await asyncio.sleep(0)
    assert slow_started.is_set()
    slow_release.set()
    if spawned:
        await asyncio.gather(*spawned, return_exceptions=True)


@pytest.mark.asyncio
async def test_create_dynamic_target_rejects_duplicate_before_bilibili(monkeypatch):
    from fastapi import HTTPException

    import admin.api.v1.targets as targets_api
    from admin.schemas.targets import DynamicTargetCreate

    body = DynamicTargetCreate(uid="123", group_ids=["1"], user_ids=[])

    mock_session = MagicMock()
    mock_session.begin = MagicMock(return_value=AsyncMock())
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_session.scalar = AsyncMock(return_value=MagicMock())

    resolve_mock = AsyncMock(return_value="昵称")
    monkeypatch.setattr(targets_api, "get_session", lambda: mock_session)
    monkeypatch.setattr(targets_api, "resolve_dynamic_target_name", resolve_mock)

    with pytest.raises(HTTPException) as exc_info:
        await targets_api.create_dynamic_target(body, MagicMock())

    assert exc_info.value.status_code == 409
    resolve_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_dynamic_target_rejects_missing_recipients_before_bilibili(
    monkeypatch,
):
    from fastapi import HTTPException

    import admin.api.v1.targets as targets_api
    from admin.schemas.targets import DynamicTargetCreate

    body = DynamicTargetCreate(uid="123", group_ids=[], user_ids=[])

    resolve_mock = AsyncMock(return_value="昵称")
    monkeypatch.setattr(targets_api, "resolve_dynamic_target_name", resolve_mock)

    with pytest.raises(HTTPException) as exc_info:
        await targets_api.create_dynamic_target(body, MagicMock())

    assert exc_info.value.status_code == 400
    assert "群组或好友" in str(exc_info.value.detail)
    resolve_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_live_target_rejects_duplicate_before_bilibili(monkeypatch):
    from fastapi import HTTPException

    import admin.api.v1.targets as targets_api
    from admin.schemas.targets import LiveTargetCreate

    body = LiveTargetCreate(room_id="123", group_ids=["1"], user_ids=[])

    mock_session = MagicMock()
    mock_session.begin = MagicMock(return_value=AsyncMock())
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_session.scalar = AsyncMock(return_value=MagicMock())

    resolve_mock = AsyncMock(return_value="主播")
    monkeypatch.setattr(targets_api, "get_session", lambda: mock_session)
    monkeypatch.setattr(targets_api, "resolve_live_target_name", resolve_mock)

    with pytest.raises(HTTPException) as exc_info:
        await targets_api.create_live_target(body, MagicMock())

    assert exc_info.value.status_code == 409
    resolve_mock.assert_not_called()
