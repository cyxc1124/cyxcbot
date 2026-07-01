"""Tests for ConfigService.load() query consolidation and reload single-flight."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import nonebot
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.config.types import AppConfigSnapshot


def _shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


def _model_column_is_real(model_cls: type, attr: str) -> bool:
    column = getattr(model_cls, attr, None)
    return column is not None and not isinstance(column, MagicMock)


def _ensure_real_db_modules():
    existing = sys.modules.get("shared.db.models")
    if existing is not None and not isinstance(existing, MagicMock):
        user = getattr(existing, "User", None)
        if user is not None and not isinstance(user, MagicMock):
            from shared.config.service import ConfigService
            from shared.db.base import Model
            from shared.db.models import (
                DynamicTarget,
                DynamicTargetGroup,
                DynamicTargetUser,
                LiveTarget,
                LiveTargetGroup,
                LiveTargetUser,
                SystemSetting,
            )

            if _model_column_is_real(DynamicTarget, "uid") and _model_column_is_real(
                LiveTarget, "room_id"
            ):
                return (
                    ConfigService,
                    Model,
                    DynamicTarget,
                    DynamicTargetGroup,
                    DynamicTargetUser,
                    LiveTarget,
                    LiveTargetGroup,
                    LiveTargetUser,
                    SystemSetting,
                )

    for name in (
        "shared.config.service",
        "shared.db.models",
        "shared.db.base",
        "nonebot_plugin_orm",
    ):
        sys.modules.pop(name, None)

    os.environ["SQLALCHEMY_DATABASE_URL"] = _shared_sqlite_url()
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=os.environ["SQLALCHEMY_DATABASE_URL"],
            alembic_startup_check=False,
        )
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")

    import shared.db.base  # noqa: F401 — register ORM metadata
    from shared.config.service import ConfigService
    from shared.db.base import Model
    from shared.db.models import (
        DynamicTarget,
        DynamicTargetGroup,
        DynamicTargetUser,
        LiveTarget,
        LiveTargetGroup,
        LiveTargetUser,
        SystemSetting,
    )

    return (
        ConfigService,
        Model,
        DynamicTarget,
        DynamicTargetGroup,
        DynamicTargetUser,
        LiveTarget,
        LiveTargetGroup,
        LiveTargetUser,
        SystemSetting,
    )


def _attach_select_counter(engine) -> tuple[dict[str, int], Callable[[], None]]:
    counter = {"select": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["select"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _before_cursor_execute)

    def cleanup() -> None:
        event.remove(
            engine.sync_engine, "before_cursor_execute", _before_cursor_execute
        )

    return counter, cleanup


@pytest.fixture
async def db_context():
    (
        ConfigService,
        Model,
        DynamicTarget,
        DynamicTargetGroup,
        DynamicTargetUser,
        LiveTarget,
        LiveTargetGroup,
        LiveTargetUser,
        SystemSetting,
    ) = _ensure_real_db_modules()

    engine = create_async_engine(_shared_sqlite_url())
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield (
            engine,
            factory,
            ConfigService,
            DynamicTarget,
            DynamicTargetGroup,
            DynamicTargetUser,
            LiveTarget,
            LiveTargetGroup,
            LiveTargetUser,
            SystemSetting,
        )
    finally:
        await engine.dispose()


async def _seed_targets(
    factory: async_sessionmaker[AsyncSession],
    *,
    DynamicTarget: type,
    DynamicTargetGroup: type,
    DynamicTargetUser: type,
    LiveTarget: type,
    LiveTargetGroup: type,
    LiveTargetUser: type,
    count: int,
) -> None:
    async with factory() as session:
        async with session.begin():
            for i in range(count):
                uid = f"d{i:04d}"
                room_id = f"l{i:04d}"
                enabled = i % 5 != 0
                dynamic = DynamicTarget(
                    uid=uid,
                    enabled=enabled,
                    at_all=bool(i % 2),
                )
                live = LiveTarget(
                    room_id=room_id,
                    enabled=enabled,
                    at_all=bool(i % 3),
                )
                session.add(dynamic)
                session.add(live)
                await session.flush()
                session.add(
                    DynamicTargetGroup(
                        dynamic_target_id=dynamic.id,
                        group_id=f"g{i % 3}",
                    )
                )
                session.add(
                    DynamicTargetUser(
                        dynamic_target_id=dynamic.id,
                        user_id=f"u{i % 4}",
                    )
                )
                session.add(
                    LiveTargetGroup(
                        live_target_id=live.id,
                        group_id=f"g{i % 3}",
                    )
                )
                session.add(
                    LiveTargetUser(
                        live_target_id=live.id,
                        user_id=f"u{i % 4}",
                    )
                )


@pytest.mark.asyncio
async def test_config_load_uses_few_select_queries_with_many_targets(
    db_context: tuple[Any, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        engine,
        factory,
        ConfigService,
        DynamicTarget,
        DynamicTargetGroup,
        DynamicTargetUser,
        LiveTarget,
        LiveTargetGroup,
        LiveTargetUser,
        _,
    ) = db_context

    await _seed_targets(
        factory,
        DynamicTarget=DynamicTarget,
        DynamicTargetGroup=DynamicTargetGroup,
        DynamicTargetUser=DynamicTargetUser,
        LiveTarget=LiveTarget,
        LiveTargetGroup=LiveTargetGroup,
        LiveTargetUser=LiveTargetUser,
        count=120,
    )

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )
    monkeypatch.setattr(
        "shared.config.service.apply_nonebot_superusers",
        lambda _users: None,
    )

    counter, cleanup = _attach_select_counter(engine)
    try:
        service = ConfigService()
        snapshot = await service.load()
    finally:
        cleanup()

    enabled_count = 120 - (120 // 5)
    assert len(snapshot.dynamic_monitor_mapping) == enabled_count
    assert len(snapshot.live_monitor_mapping) == enabled_count
    # settings + dynamic (+ groups/users selectinload) + live enabled
    # (+ groups/users selectinload) + link parser policies
    assert counter["select"] <= 9


@pytest.mark.asyncio
async def test_config_load_derives_subscription_mappings_from_all_targets(
    db_context: tuple[Any, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        _,
        factory,
        ConfigService,
        DynamicTarget,
        DynamicTargetGroup,
        DynamicTargetUser,
        *_,
    ) = db_context

    async with factory() as session:
        async with session.begin():
            enabled = DynamicTarget(uid="111", enabled=True, at_all=True)
            disabled = DynamicTarget(uid="222", enabled=False, at_all=False)
            session.add(enabled)
            session.add(disabled)
            await session.flush()
            session.add(DynamicTargetGroup(dynamic_target_id=enabled.id, group_id="g1"))
            session.add(
                DynamicTargetGroup(dynamic_target_id=disabled.id, group_id="g2")
            )
            session.add(DynamicTargetUser(dynamic_target_id=enabled.id, user_id="u1"))

    monkeypatch.setattr(
        "shared.config.service.get_session",
        lambda: factory(),
    )
    monkeypatch.setattr(
        "shared.config.service.apply_nonebot_superusers",
        lambda _users: None,
    )

    service = ConfigService()
    snapshot = await service.load()

    assert snapshot.dynamic_monitor_mapping == {"111": ["g1"]}
    assert snapshot.dynamic_subscription_mapping == {"111": ["g1"], "222": ["g2"]}
    assert snapshot.dynamic_subscription_user_mapping == {"111": ["u1"]}
    assert snapshot.dynamic_at_all == {"111": True}


@pytest.mark.asyncio
async def test_reload_single_flight_coalesces_concurrent_calls() -> None:
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    load_calls = 0
    snapshot = AppConfigSnapshot()

    async def slow_load() -> AppConfigSnapshot:
        nonlocal load_calls
        load_calls += 1
        await asyncio.sleep(0.05)
        return snapshot

    svc.load = slow_load  # type: ignore[method-assign]

    first, second, third = await asyncio.gather(
        svc.reload(),
        svc.reload(),
        svc.reload(),
    )

    assert 1 <= load_calls <= 2
    assert first is snapshot
    assert second is snapshot
    assert third is snapshot


@pytest.mark.asyncio
async def test_reload_during_callbacks_schedules_trailing_load() -> None:
    """Reload requested after load() but before callbacks finish must re-read DB."""
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    load_calls = 0
    stale = AppConfigSnapshot(dynamic_monitor_mapping={"a": ["g1"]})
    fresh = AppConfigSnapshot(dynamic_monitor_mapping={"b": ["g2"]})
    callback_started = asyncio.Event()
    callback_release = asyncio.Event()

    async def load_once_then_fresh() -> AppConfigSnapshot:
        nonlocal load_calls
        load_calls += 1
        return stale if load_calls == 1 else fresh

    async def slow_callback(_snapshot: AppConfigSnapshot) -> None:
        callback_started.set()
        await callback_release.wait()

    svc.load = load_once_then_fresh  # type: ignore[method-assign]
    svc.register_reload_callback(slow_callback)

    first_task = asyncio.create_task(svc.reload())
    await callback_started.wait()
    second_task = asyncio.create_task(svc.reload())
    await asyncio.sleep(0.01)
    callback_release.set()
    first_result, second_result = await asyncio.gather(first_task, second_task)

    assert load_calls == 2
    assert first_result.dynamic_monitor_mapping == {"b": ["g2"]}
    assert second_result.dynamic_monitor_mapping == {"b": ["g2"]}


@pytest.mark.asyncio
async def test_reload_single_flight_runs_again_after_previous_completes() -> None:
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    load_calls = 0
    snapshot = AppConfigSnapshot()

    async def counting_load() -> AppConfigSnapshot:
        nonlocal load_calls
        load_calls += 1
        return snapshot

    svc.load = counting_load  # type: ignore[method-assign]

    await svc.reload()
    await svc.reload()

    assert load_calls == 2
