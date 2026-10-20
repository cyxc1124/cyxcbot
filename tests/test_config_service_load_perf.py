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
    # (+ groups/users selectinload) + x enabled (+ groups/users selectinload)
    # + bilibili/douyin link parser + rust rcon (+ custom commands)
    assert counter["select"] <= 18


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


@pytest.mark.asyncio
async def test_reload_survives_caller_cancellation() -> None:
    """One cancelled waiter must not abort the shared reload for others."""
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    load_calls = 0
    snapshot = AppConfigSnapshot(dynamic_monitor_mapping={"ok": ["g1"]})
    callback_started = asyncio.Event()
    callback_release = asyncio.Event()

    async def counting_load() -> AppConfigSnapshot:
        nonlocal load_calls
        load_calls += 1
        svc._snapshot = snapshot
        return snapshot

    async def slow_callback(_snapshot: AppConfigSnapshot) -> None:
        callback_started.set()
        await callback_release.wait()

    svc.load = counting_load  # type: ignore[method-assign]
    svc.register_reload_callback(slow_callback)

    leader = asyncio.create_task(svc.reload())
    await callback_started.wait()

    cancelled_waiter = asyncio.create_task(svc.reload())
    await asyncio.sleep(0.01)
    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter

    assert not leader.done()
    callback_release.set()
    result = await leader

    assert result.dynamic_monitor_mapping == {"ok": ["g1"]}
    assert svc.snapshot.dynamic_monitor_mapping == {"ok": ["g1"]}
    # coalesced caller may set _reload_pending before cancel → at most one extra load
    assert 1 <= load_calls <= 2


@pytest.mark.asyncio
async def test_shielded_shared_task_not_cancelled_by_waiter() -> None:
    """Direct shield await on the shared task survives waiter cancellation."""
    from shared.config.service import ConfigService

    svc = ConfigService.get_instance()
    svc._reload_callbacks.clear()
    load_calls = 0
    snapshot = AppConfigSnapshot()
    callback_started = asyncio.Event()
    callback_release = asyncio.Event()

    async def counting_load() -> AppConfigSnapshot:
        nonlocal load_calls
        load_calls += 1
        svc._snapshot = snapshot
        return snapshot

    async def slow_callback(_snapshot: AppConfigSnapshot) -> None:
        callback_started.set()
        await callback_release.wait()

    svc.load = counting_load  # type: ignore[method-assign]
    svc.register_reload_callback(slow_callback)

    leader = asyncio.create_task(svc.reload())
    await callback_started.wait()
    async with svc._reload_lock:
        shared = svc._reload_task
    assert shared is not None

    async def wait_shielded() -> None:
        await asyncio.shield(shared)

    cancelled_waiter = asyncio.create_task(wait_shielded())
    await asyncio.sleep(0.01)
    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter

    assert not shared.cancelled()
    assert not shared.done()
    callback_release.set()
    await leader
    assert load_calls == 1


@pytest.mark.asyncio
async def test_official_settings_permissions_and_friend_cache_round_trip(
    db_context, monkeypatch
):
    from fastapi import HTTPException
    from sqlalchemy import select

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.adapter import sessions
    from shared.config.nonebot_superusers import apply_nonebot_superusers
    from shared.db.models import OfficialQQSession

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(nonebot.get_driver().config, "superusers", set())
    assert not (await service.load()).official_qq_use_websocket
    users = ["12345", "USER_OPENID_123"]
    updated = await settings_api.update_settings(
        SettingsUpdateRequest(
            nonebot_superusers=users,
            status_check_allowed_qq=users,
            official_qq_app_id="test-app",
            official_qq_app_secret="test-only-app-secret",
        ),
        None,
    )
    assert updated.nonebot_superusers == users
    assert updated.status_check_allowed_qq == users
    assert updated.official_qq.secret.configured
    assert "test-only-app-secret" not in updated.model_dump_json()
    assert service.get_snapshot().official_qq_app_secret == "test-only-app-secret"
    apply_nonebot_superusers(service.get_snapshot().nonebot_superusers)
    assert nonebot.get_driver().config.superusers == set(users)
    async with factory() as session:
        stored = await session.get(SystemSetting, "official_qq_app_secret_encrypted")
        assert stored.value and stored.value != "test-only-app-secret"
    with pytest.raises(HTTPException) as exc:
        await settings_api.update_settings(
            SettingsUpdateRequest(nonebot_superusers=["invalid id!"]), None
        )
    assert exc.value.status_code == 400
    assert service.get_snapshot().nonebot_superusers == users

    monkeypatch.setattr(sessions, "_orm_session", lambda: factory())
    monkeypatch.setattr(sessions, "_session_model", lambda: OfficialQQSession)
    await sessions.upsert_session("USER_OPENID_123", "c2c")
    assert [row.openid for row in await sessions.list_sessions("c2c")] == [
        "USER_OPENID_123"
    ]
    await sessions.delete_session("USER_OPENID_123")
    async with factory() as session:
        assert not (await session.scalars(select(OfficialQQSession))).all()

    cleared = await settings_api.update_settings(
        SettingsUpdateRequest(official_qq_app_id="", official_qq_app_secret=""), None
    )
    assert not cleared.official_qq.secret.configured
    assert not service.get_snapshot().official_qq_app_secret


@pytest.mark.asyncio
async def test_bot_connections_endpoint_skips_bilibili_and_requires_admin(
    db_context, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from admin.api.v1 import connections as connections_api
    from admin.deps import get_current_user, require_setup_complete

    qq = {"connected": True, "bot_count": 1, "bots": [], "message": "已连接"}
    official = {"configured": False, "connected": False, "message": "未配置"}
    onebot_status = AsyncMock(return_value=qq)
    official_status = AsyncMock(return_value=official)
    full_status = AsyncMock(side_effect=AssertionError("must not check Bilibili"))
    monkeypatch.setattr(connections_api, "get_qq_connection_status", onebot_status)
    monkeypatch.setattr(
        connections_api, "get_official_qq_connection_status", official_status
    )
    monkeypatch.setattr(connections_api, "get_connections_status", full_status)
    app = FastAPI()
    app.include_router(connections_api.router)
    app.dependency_overrides[require_setup_complete] = lambda: None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/connections/bots")).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            is_admin=False
        )
        assert (await client.get("/connections/bots")).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            is_admin=True
        )
        response = await client.get("/connections/bots")

    assert response.status_code == 200
    assert response.json()["qq"] == qq
    assert response.json()["official_qq"]["configured"] is False
    assert "bilibili" not in response.json()
    onebot_status.assert_awaited_once_with(include_login_info=False)
    official_status.assert_awaited_once()
    full_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_connections_endpoint_does_not_probe_onebot_api(
    db_context, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from admin.api.v1 import connections as connections_api
    from admin.services import connection_status

    bot = SimpleNamespace(
        self_id="10001", call_api=AsyncMock(side_effect=AssertionError("no API probe"))
    )
    monkeypatch.setattr(connection_status, "iter_onebot_bots", lambda: [bot])
    monkeypatch.setattr(
        connections_api,
        "get_official_qq_connection_status",
        AsyncMock(
            return_value={"configured": False, "connected": False, "message": "未配置"}
        ),
    )

    result = await connections_api.bot_connections_status(None)

    assert result.qq.connected
    assert result.qq.bot_count == 1
    assert result.qq.message == "已连接 1 个 OneBot 实例"
    bot.call_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_full_onebot_status_keeps_login_info(db_context, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from admin.services import connection_status

    bot = SimpleNamespace(
        self_id="10001",
        call_api=AsyncMock(return_value={"user_id": 10001, "nickname": "示例机器人"}),
    )
    monkeypatch.setattr(connection_status, "iter_onebot_bots", lambda: [bot])

    result = await connection_status.get_qq_connection_status()

    assert result["bots"] == [{"qq": "10001", "nickname": "示例机器人"}]
    bot.call_api.assert_awaited_once_with("get_login_info")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configured", "bot_ids", "connected"),
    [
        (True, ["old-app"], False),
        (False, ["current-app"], False),
        (True, ["current-app"], True),
        (True, [], False),
        (True, ["old-app", "current-app"], True),
    ],
)
async def test_official_connection_status_matches_configured_app(
    db_context, monkeypatch, configured, bot_ids, connected
):
    from types import SimpleNamespace

    from admin.services import connection_status

    snapshot = SimpleNamespace(
        official_qq_app_id="current-app",
        official_qq_app_secret_set=configured,
        official_qq_use_websocket=True,
    )
    monkeypatch.setattr(
        connection_status,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: snapshot),
    )
    monkeypatch.setattr(
        connection_status,
        "iter_official_bots",
        lambda: [SimpleNamespace(self_id=bot_id) for bot_id in bot_ids],
    )

    result = await connection_status.get_official_qq_connection_status()

    assert result["connected"] is connected
    assert result["configured"] is configured


@pytest.mark.asyncio
async def test_official_sandbox_legacy_read_and_patch_compatibility(
    db_context, monkeypatch
):
    from unittest.mock import AsyncMock

    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from admin.services import connection_status

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(connection_status, "get_config_service", lambda: service)
    monkeypatch.setattr(connection_status, "iter_official_bots", lambda: [])
    await service.set_settings(
        {"official_qq_is_sandbox": "true", "official_qq_app_id": "existing-app"}
    )
    await service.load()
    callback = AsyncMock()
    service.register_reload_callback(callback)

    assert not (await settings_api.get_settings(None)).official_qq.is_sandbox
    assert not (await connection_status.get_official_qq_connection_status())[
        "is_sandbox"
    ]
    with pytest.raises(HTTPException, match="沙箱") as exc:
        await settings_api.update_settings(
            SettingsUpdateRequest(
                official_qq_is_sandbox=True, official_qq_app_id="must-not-save"
            ),
            None,
        )
    assert exc.value.status_code == 400
    assert service.get_snapshot().official_qq_app_id == "existing-app"
    callback.assert_not_awaited()
    async with factory() as session:
        assert (
            await session.get(SystemSetting, "official_qq_app_id")
        ).value == "existing-app"
        assert (
            await session.get(SystemSetting, "official_qq_is_sandbox")
        ).value == "true"

    updated = await settings_api.update_settings(
        SettingsUpdateRequest(official_qq_is_sandbox=False), None
    )
    assert not updated.official_qq.is_sandbox
    callback.assert_awaited_once()
    async with factory() as session:
        assert (
            await session.get(SystemSetting, "official_qq_is_sandbox")
        ).value == "false"


@pytest.mark.asyncio
async def test_settings_validates_aliases_with_proposed_prefixes(
    db_context, monkeypatch
):
    import json

    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    await service.load()
    aliases = {"live_status": {"triggers": ["/status"]}}
    with pytest.raises(HTTPException, match="触发词冲突") as exc:
        await settings_api.update_settings(
            SettingsUpdateRequest(command_aliases=aliases), None
        )
    assert exc.value.status_code == 400
    async with factory() as session:
        assert await session.get(SystemSetting, "command_aliases") is None

    saved = await settings_api.update_settings(
        SettingsUpdateRequest(
            command_aliases={"live_status": {"triggers": ["~status"]}},
            command_extra_prefixes=[],
        ),
        None,
    )
    assert saved.command_extra_prefixes == []
    with pytest.raises(HTTPException, match="触发词冲突"):
        await settings_api.update_settings(
            SettingsUpdateRequest(command_extra_prefixes=["~"]), None
        )
    async with factory() as session:
        assert (
            json.loads(
                (await session.get(SystemSetting, "command_extra_prefixes")).value
            )
            == []
        )
    saved = await settings_api.update_settings(
        SettingsUpdateRequest(
            command_aliases={"live_status": {"triggers": ["~直播状态"]}},
            command_extra_prefixes=["~"],
        ),
        None,
    )
    assert saved.command_extra_prefixes == ["~"]
    assert saved.command_aliases["live_status"].triggers == ["~直播状态"]


@pytest.mark.asyncio
@pytest.mark.parametrize("command_id", ["dynamic_extract", "group_special_title"])
async def test_settings_accepts_prefix_required_argument_alias(
    db_context, monkeypatch, command_id
):
    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest

    _, factory, ConfigService, *_ = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    await service.load()
    saved = await settings_api.update_settings(
        SettingsUpdateRequest(command_aliases={command_id: {"triggers": ["/status"]}}),
        None,
    )
    assert saved.command_aliases[command_id].triggers == ["/status"]
    await service.load()
    assert service.get_snapshot().command_aliases[command_id].triggers == ["/status"]


@pytest.mark.asyncio
@pytest.mark.parametrize("collision_kind", ["binding", "custom"])
async def test_prefix_only_patch_preserves_legacy_rcon_alias_collisions(
    db_context, monkeypatch, collision_kind
):
    import json

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.db.models import RustRconBinding, RustRconCustomCommand

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    async with factory() as session, session.begin():
        binding = RustRconBinding(
            alias="status" if collision_kind == "binding" else "rcon1", host="localhost"
        )
        session.add(binding)
        await session.flush()
        if collision_kind == "custom":
            session.add(
                RustRconCustomCommand(
                    name="status", template="status", binding_id=binding.id
                )
            )
    await service.load()
    saved = await settings_api.update_settings(
        SettingsUpdateRequest(command_extra_prefixes=[]), None
    )
    assert saved.command_extra_prefixes == []
    saved = await settings_api.update_settings(
        SettingsUpdateRequest(
            command_aliases={"live_status": {"triggers": ["直播状态"]}}
        ),
        None,
    )
    assert saved.command_aliases["live_status"].triggers == ["直播状态"]
    async with factory() as session:
        assert (
            json.loads(
                (await session.get(SystemSetting, "command_extra_prefixes")).value
            )
            == []
        )
        assert await session.get(SystemSetting, "command_aliases") is not None


@pytest.mark.asyncio
async def test_settings_rejects_reverse_prefix_required_argument_overlap(
    db_context, monkeypatch
):
    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    await service.load()
    aliases = {
        "status": {"enabled": False},
        "live_status": {"triggers": ["/status"]},
        "group_special_title": {"triggers": ["status"]},
    }
    with pytest.raises(HTTPException, match="触发词冲突") as exc:
        await settings_api.update_settings(
            SettingsUpdateRequest(command_aliases=aliases), None
        )
    assert exc.value.status_code == 400
    async with factory() as session:
        assert await session.get(SystemSetting, "command_aliases") is None
    aliases["group_special_title"]["enabled"] = False
    saved = await settings_api.update_settings(
        SettingsUpdateRequest(command_aliases=aliases), None
    )
    assert saved.command_aliases["live_status"].triggers == ["/status"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "trigger,name,old_prefixes,new_prefixes,rejected",
    [
        ("status", "!status", [], ["!"], True),
        ("!status", "status", [], ["!"], True),
        ("status", "!!status", ["!"], ["!", "!!"], True),
        ("!rcon1 status", "rcon1", [], ["!"], True),
        ("con1 status", "rcon1", [], ["r"], True),
        ("!status", ".status", [], ["!", "."], True),
        ("status", "!status", [], ["!", "!sta"], True),
        ("status", "!status", ["!"], [], False),
        ("status", "status", [], ["~"], True),
    ],
)
async def test_prefix_patch_rejects_new_inputs_in_either_chat_scope(
    db_context, monkeypatch, trigger, name, old_prefixes, new_prefixes, rejected
):
    import json

    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.config.command_aliases import (
        normalize_command_aliases,
        serialize_command_aliases,
    )
    from shared.db.models import RustRconBinding

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    aliases = normalize_command_aliases({"status": {"triggers": [trigger]}})
    await service.set_settings(
        {
            "command_extra_prefixes": json.dumps(old_prefixes),
            "command_aliases": json.dumps(serialize_command_aliases(aliases)),
        }
    )
    async with factory() as session, session.begin():
        binding = RustRconBinding(alias=name, host="localhost")
        session.add(binding)
        await session.flush()
    await service.load()
    body = SettingsUpdateRequest(command_extra_prefixes=new_prefixes)
    if rejected:
        with pytest.raises(HTTPException, match="冲突") as exc:
            await settings_api.update_settings(body, None)
        assert exc.value.status_code == 400
    else:
        saved = await settings_api.update_settings(body, None)
        assert saved.command_extra_prefixes == new_prefixes
    async with factory() as session:
        assert json.loads(
            (await session.get(SystemSetting, "command_extra_prefixes")).value
        ) == (old_prefixes if rejected else new_prefixes)
    assert service.get_snapshot().command_extra_prefixes == (
        old_prefixes if rejected else new_prefixes
    )


@pytest.mark.asyncio
async def test_prefix_patch_rejects_new_private_extract_rcon_collision(
    db_context, monkeypatch
):
    import json

    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.db.models import RustRconBinding

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    await service.set_settings({"command_extra_prefixes": "[]"})
    async with factory() as session, session.begin():
        binding = RustRconBinding(
            alias="!提取1234567890",
            host="localhost",
        )
        session.add(binding)
        await session.flush()
    await service.load()
    with pytest.raises(HTTPException, match="冲突") as exc:
        await settings_api.update_settings(
            SettingsUpdateRequest(command_extra_prefixes=["!"]), None
        )
    assert exc.value.status_code == 400
    async with factory() as session:
        assert (
            json.loads(
                (await session.get(SystemSetting, "command_extra_prefixes")).value
            )
            == []
        )


@pytest.mark.asyncio
async def test_prefix_only_patch_preserves_legacy_group_only_custom_collision(
    db_context, monkeypatch
):
    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.db.models import RustRconBinding, RustRconCustomCommand

    _, factory, ConfigService, *_ = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    await service.set_settings({"command_extra_prefixes": '["!"]'})
    async with factory() as session, session.begin():
        binding = RustRconBinding(alias="rcon1", host="localhost")
        session.add(binding)
        await session.flush()
        session.add(
            RustRconCustomCommand(
                name="!status", template="status", binding_id=binding.id
            )
        )
    await service.load()
    saved = await settings_api.update_settings(
        SettingsUpdateRequest(command_extra_prefixes=[]), None
    )
    assert saved.command_extra_prefixes == []
    saved = await settings_api.update_settings(
        SettingsUpdateRequest(
            command_aliases={"live_status": {"triggers": ["直播状态"]}}
        ),
        None,
    )
    assert saved.command_aliases["live_status"].triggers == ["直播状态"]


@pytest.mark.asyncio
@pytest.mark.parametrize("custom", [False, True], ids=["binding", "custom"])
@pytest.mark.parametrize(
    "cid,trigger,name,old_prefixes,new_prefixes,enabled,parent_enabled,rejected",
    [
        ("status", "status", "server", [], ["$"], True, True, True),
        ("live_monitor_list", "list", "server", [], ["$"], True, True, True),
        ("status", "status", "server", ["$"], [], True, True, False),
        ("status", "status", "server", ["$"], ["$"], True, True, False),
        ("rust_player_bind", "!bind", "bind", ["!"], ["!", "$"], True, True, False),
        ("rust_player_bind", "!bind", "bind", ["!", "!bin"], ["!"], True, True, True),
        ("live_monitor_list", "!list", "list", [], ["!"], True, True, True),
        ("live_status", "!live", "live", [], ["!"], True, True, True),
        ("dynamic_query_latest", "!latest", "latest", [], ["!"], True, True, True),
        ("dynamic_query_pinned", "!pinned", "pinned", [], ["!"], True, True, True),
        ("video_query_latest", "!video", "video", [], ["!"], True, True, True),
        ("group_special_title", "头衔", "!头衔", [], ["!"], True, True, True),
        ("rust_player_bind", "!bind", "bind", [], ["!"], True, True, True),
        ("rust_player_checkin", "!checkin", "checkin", [], ["!"], True, True, True),
        ("rust_player_points", "!points", "points", [], ["!"], True, True, True),
        ("rust_player_shop_list", "!items", "items", [], ["!"], True, True, True),
        ("rust_player_shop_redeem", "!redeem", "redeem", [], ["!"], True, True, True),
        ("live_monitor_list", "list", "!list", [], ["!"], True, True, True),
        ("live_monitor_list", "!list", "list", ["!"], ["!"], True, True, False),
        ("live_monitor_list", "!list", "list", ["!"], [], True, True, False),
        ("rust_player_bind", "!bind", "bind", [], ["!", "!bin"], True, True, False),
        ("rust_player_bind", "!bind", ".bind", [], ["!", "."], True, True, False),
        ("live_monitor_list", "!list", "list", [], ["!"], False, True, False),
        ("live_monitor_list", "!list", "list", [], ["!"], True, False, False),
    ],
)
async def test_prefix_patch_compares_group_rcon_collisions_separately(
    db_context,
    monkeypatch,
    custom,
    cid,
    trigger,
    name,
    old_prefixes,
    new_prefixes,
    enabled,
    parent_enabled,
    rejected,
):
    import json

    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.config.command_aliases import (
        COMMAND_DEFAULTS,
        normalize_command_aliases,
        serialize_command_aliases,
    )
    from shared.db.models import RustRconBinding, RustRconCustomCommand

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    raw_aliases = {command_id: {"enabled": False} for command_id in COMMAND_DEFAULTS}
    raw_aliases[cid] = {"triggers": [trigger], "enabled": enabled}
    aliases = normalize_command_aliases(raw_aliases)
    await service.set_settings(
        {
            "command_extra_prefixes": json.dumps(old_prefixes),
            "command_aliases": json.dumps(serialize_command_aliases(aliases)),
        }
    )
    async with factory() as session, session.begin():
        binding = RustRconBinding(
            alias="rcon1" if custom else name,
            host="localhost",
            enabled=parent_enabled,
        )
        session.add(binding)
        await session.flush()
        if custom:
            session.add(
                RustRconCustomCommand(
                    name=name, template="status", binding_id=binding.id
                )
            )
    await service.load()
    body = SettingsUpdateRequest(command_extra_prefixes=new_prefixes)
    if rejected:
        with pytest.raises(HTTPException, match="冲突") as exc:
            await settings_api.update_settings(body, None)
        assert exc.value.status_code == 400
    else:
        saved = await settings_api.update_settings(body, None)
        assert saved.command_extra_prefixes == new_prefixes
    expected = old_prefixes if rejected else new_prefixes
    async with factory() as session:
        assert (
            json.loads(
                (await session.get(SystemSetting, "command_extra_prefixes")).value
            )
            == expected
        )
    assert service.get_snapshot().command_extra_prefixes == expected


@pytest.mark.asyncio
async def test_prefix_patch_compares_group_custom_extract_grammar(
    db_context, monkeypatch
):
    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.db.models import RustRconBinding, RustRconCustomCommand

    _, factory, ConfigService, *_ = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    await service.set_settings({"command_extra_prefixes": "[]"})
    async with factory() as session, session.begin():
        binding = RustRconBinding(alias="rcon1", host="localhost")
        session.add(binding)
        await session.flush()
        session.add(
            RustRconCustomCommand(
                name="!提取1234567890", template="status", binding_id=binding.id
            )
        )
    await service.load()
    with pytest.raises(HTTPException, match="冲突") as exc:
        await settings_api.update_settings(
            SettingsUpdateRequest(command_extra_prefixes=["!"]), None
        )
    assert exc.value.status_code == 400
    assert service.get_snapshot().command_extra_prefixes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("custom", [False, True], ids=["binding", "custom"])
@pytest.mark.parametrize(
    "cid,old_trigger,old_enabled,patch,name,old_prefixes,new_prefixes,parent_enabled,rejected",
    [
        (
            "live_status",
            "live",
            True,
            {"triggers": ["server"]},
            "server",
            ["!"],
            None,
            True,
            True,
        ),
        (
            "live_status",
            "live",
            True,
            {"triggers": ["!server"]},
            "server",
            ["!"],
            None,
            True,
            True,
        ),
        (
            "live_status",
            "!server",
            False,
            {"enabled": True},
            "server",
            ["!"],
            None,
            True,
            True,
        ),
        (
            "live_status",
            "live",
            True,
            {"triggers": ["!server"]},
            "server",
            [],
            ["!"],
            True,
            True,
        ),
        (
            "status",
            "status",
            True,
            {"triggers": ["!server"]},
            "server",
            ["!"],
            None,
            True,
            True,
        ),
        (
            "dynamic_extract",
            "提取",
            True,
            {"triggers": ["server"]},
            "!server1234567890",
            ["!"],
            None,
            True,
            True,
        ),
        (
            "group_special_title",
            "头衔",
            True,
            {"triggers": ["server"]},
            "server",
            ["!"],
            None,
            True,
            True,
        ),
        (
            "live_status",
            "server",
            True,
            {"triggers": ["server"]},
            "server",
            ["!"],
            None,
            True,
            False,
        ),
        (
            "live_status",
            "server",
            True,
            {"enabled": True},
            "server",
            ["!"],
            None,
            True,
            False,
        ),
        (
            "live_status",
            "server",
            True,
            {"triggers": ["safe"]},
            "server",
            ["!"],
            None,
            True,
            False,
        ),
        (
            "live_status",
            "server",
            True,
            {"enabled": False},
            "server",
            ["!"],
            None,
            True,
            False,
        ),
        (
            "live_status",
            "server",
            True,
            {"triggers": ["!server"]},
            "server",
            ["!"],
            [],
            True,
            False,
        ),
        (
            "live_status",
            "live",
            True,
            {"triggers": ["!server"]},
            "server",
            [],
            None,
            True,
            False,
        ),
        (
            "live_status",
            "live",
            True,
            {"triggers": ["!server"]},
            "server",
            ["!", "!ser"],
            None,
            True,
            False,
        ),
        (
            "rust_player_bind",
            "bind",
            True,
            {"triggers": ["!server"]},
            ".server",
            ["!", "."],
            None,
            True,
            False,
        ),
        (
            "live_status",
            "live",
            True,
            {"triggers": ["!server"]},
            "server",
            ["!"],
            None,
            False,
            False,
        ),
    ],
)
async def test_alias_patch_compares_actual_old_and_new_rcon_grammars(
    db_context,
    monkeypatch,
    custom,
    cid,
    old_trigger,
    old_enabled,
    patch,
    name,
    old_prefixes,
    new_prefixes,
    parent_enabled,
    rejected,
):
    import json

    from fastapi import HTTPException

    from admin.api.v1 import settings as settings_api
    from admin.schemas.settings import SettingsUpdateRequest
    from shared.config.command_aliases import (
        COMMAND_DEFAULTS,
        normalize_command_aliases,
        serialize_command_aliases,
    )
    from shared.db.models import RustRconBinding, RustRconCustomCommand

    _, factory, ConfigService, *_, SystemSetting = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(settings_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    aliases = normalize_command_aliases(
        {
            command_id: {
                "enabled": command_id == cid and old_enabled,
                "triggers": [old_trigger] if command_id == cid else [],
            }
            for command_id in COMMAND_DEFAULTS
        }
    )
    original_settings = {
        "command_aliases": json.dumps(serialize_command_aliases(aliases)),
        "command_extra_prefixes": json.dumps(old_prefixes),
    }
    await service.set_settings(original_settings)
    async with factory() as session, session.begin():
        binding = RustRconBinding(
            alias="rcon1" if custom else name, host="localhost", enabled=parent_enabled
        )
        session.add(binding)
        await session.flush()
        if custom:
            session.add(
                RustRconCustomCommand(
                    name=name, template="status", binding_id=binding.id
                )
            )
    await service.load()
    body = SettingsUpdateRequest(
        command_aliases={cid: patch}, command_extra_prefixes=new_prefixes
    )
    if rejected:
        with pytest.raises(HTTPException, match="冲突") as exc:
            await settings_api.update_settings(body, None)
        assert exc.value.status_code == 400
    else:
        saved = await settings_api.update_settings(body, None)
        assert saved.command_aliases[cid].triggers == patch.get(
            "triggers", [old_trigger]
        )
        assert saved.command_aliases[cid].enabled == patch.get("enabled", old_enabled)
        assert saved.command_extra_prefixes == (
            old_prefixes if new_prefixes is None else new_prefixes
        )
    async with factory() as session:
        persisted = {
            key: (await session.get(SystemSetting, key)).value
            for key in original_settings
        }
    if rejected:
        assert persisted == original_settings
        assert serialize_command_aliases(
            service.get_snapshot().command_aliases
        ) == serialize_command_aliases(aliases)
        assert service.get_snapshot().command_extra_prefixes == old_prefixes


@pytest.mark.asyncio
@pytest.mark.parametrize("custom", [False, True], ids=["binding", "custom"])
@pytest.mark.parametrize(
    "operation",
    [
        "create",
        "rename",
        "enable",
        "raw_create",
        "disable_rename",
        "safe_rename",
        "noop",
        "metadata",
        "create_disabled",
        "longest_create",
        "delete",
    ],
)
async def test_rcon_crud_rejects_only_new_builtin_grammar_collisions(
    db_context, monkeypatch, custom, operation
):
    import json
    from unittest.mock import AsyncMock

    from fastapi import HTTPException
    from sqlalchemy import select

    from admin.api.v1 import rust_rcon as binding_api
    from admin.api.v1 import rust_rcon_custom as custom_api
    from admin.schemas.rust_rcon import RustRconBindingCreate, RustRconBindingUpdate
    from admin.schemas.rust_rcon_custom import (
        RustRconCustomCommandCreateRequest,
        RustRconCustomCommandUpdateRequest,
    )
    from shared.config.command_aliases import (
        COMMAND_DEFAULTS,
        normalize_command_aliases,
        serialize_command_aliases,
    )
    from shared.db.models import RustRconBinding, RustRconCustomCommand

    _, factory, ConfigService, *_ = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    for module in (binding_api, custom_api):
        monkeypatch.setattr(module, "get_session", lambda: factory())
        monkeypatch.setattr(module, "get_config_service", lambda: service)
    monkeypatch.setattr(binding_api, "encrypt_value", lambda value: "")
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    aliases = normalize_command_aliases(
        {
            cid: {
                "enabled": cid == "live_status",
                "triggers": ["server" if operation == "raw_create" else "!server"],
            }
            for cid in COMMAND_DEFAULTS
        }
    )
    await service.set_settings(
        {
            "command_aliases": json.dumps(serialize_command_aliases(aliases)),
            "command_extra_prefixes": json.dumps(
                ["!", "!ser"] if operation == "longest_create" else ["!"]
            ),
        }
    )
    model = RustRconCustomCommand if custom else RustRconBinding
    creating = operation in (
        "create",
        "raw_create",
        "create_disabled",
        "longest_create",
    )
    row_id = None
    async with factory() as session, session.begin():
        parent = RustRconBinding(alias="rcon1", host="localhost") if custom else None
        if parent:
            session.add(parent)
            await session.flush()
        if not creating:
            name = "safe" if operation in ("rename", "disable_rename") else "server"
            row = (
                RustRconCustomCommand(
                    name=name,
                    template="status",
                    binding_id=parent.id,
                    enabled=operation != "enable",
                )
                if custom
                else RustRconBinding(
                    alias=name, host="localhost", enabled=operation != "enable"
                )
            )
            session.add(row)
            await session.flush()
            row_id = row.id
        parent_id = parent.id if parent else None
    await service.load()
    reload = AsyncMock(wraps=service.reload)
    monkeypatch.setattr(service, "reload", reload)

    async def rows():
        async with factory() as session:
            return [
                (row.id, row.name if custom else row.alias, row.enabled)
                for row in (
                    await session.scalars(select(model).order_by(model.id))
                ).all()
            ]

    before = await rows()
    if creating:
        if custom:
            request = RustRconCustomCommandCreateRequest(
                name="server",
                template="status",
                binding_id=parent_id,
                allowed_qq_ids=["123"],
                enabled=operation != "create_disabled",
            )
            action = custom_api.create_rust_rcon_custom_command(request, None)
        else:
            request = RustRconBindingCreate(
                alias="server",
                host="localhost",
                password="test-only",
                allowed_qq_ids=["123"],
                enabled=operation != "create_disabled",
            )
            action = binding_api.create_rust_rcon_binding(request, None)
    elif operation == "delete":
        action = (
            custom_api.delete_rust_rcon_custom_command(row_id, None)
            if custom
            else binding_api.delete_rust_rcon_binding(row_id, None)
        )
    else:
        changes = {}
        if operation in ("rename", "disable_rename", "safe_rename", "noop"):
            changes["name" if custom else "alias"] = (
                "safe" if operation == "safe_rename" else "server"
            )
        if operation in ("enable", "disable_rename"):
            changes["enabled"] = operation == "enable"
        if operation == "metadata":
            changes["template" if custom else "host"] = (
                "status " if custom else "127.0.0.1"
            )
        action = (
            custom_api.update_rust_rcon_custom_command(
                row_id, RustRconCustomCommandUpdateRequest(**changes), None
            )
            if custom
            else binding_api.update_rust_rcon_binding(
                row_id, RustRconBindingUpdate(**changes), None
            )
        )
    if operation in ("create", "rename", "enable", "raw_create"):
        with pytest.raises(HTTPException, match="冲突") as exc:
            await action
        assert exc.value.status_code in (400, 409)
        assert await rows() == before
        reload.assert_not_awaited()
    else:
        await action
        reload.assert_awaited_once()
        if operation == "delete":
            assert await rows() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation,rejected",
    [("enable", True), ("rename_enable", True), ("stable_rename", False)],
)
async def test_parent_binding_enable_checks_existing_custom_grammar(
    db_context, monkeypatch, operation, rejected
):
    import json

    from fastapi import HTTPException

    from admin.api.v1 import rust_rcon as binding_api
    from admin.schemas.rust_rcon import RustRconBindingUpdate
    from shared.config.command_aliases import (
        COMMAND_DEFAULTS,
        normalize_command_aliases,
        serialize_command_aliases,
    )
    from shared.db.models import RustRconBinding, RustRconCustomCommand

    _, factory, ConfigService, *_ = db_context
    service = ConfigService()
    monkeypatch.setattr("shared.config.service.get_session", lambda: factory())
    monkeypatch.setattr(binding_api, "get_session", lambda: factory())
    monkeypatch.setattr(binding_api, "get_config_service", lambda: service)
    monkeypatch.setattr(
        "shared.config.command_aliases._configured_command_starts",
        lambda: frozenset({"/"}),
    )
    aliases = normalize_command_aliases(
        {
            cid: {"enabled": cid == "live_status", "triggers": ["!server"]}
            for cid in COMMAND_DEFAULTS
        }
    )
    await service.set_settings(
        {
            "command_aliases": json.dumps(serialize_command_aliases(aliases)),
            "command_extra_prefixes": '["!"]',
        }
    )
    async with factory() as session, session.begin():
        parent = RustRconBinding(
            alias="rcon1", host="localhost", enabled=operation == "stable_rename"
        )
        session.add(parent)
        await session.flush()
        parent_id = parent.id
        session.add(
            RustRconCustomCommand(
                name="server", template="status", binding_id=parent_id
            )
        )
    await service.load()
    changes = (
        {"enabled": True}
        if operation == "enable"
        else {"alias": "rcon2", "enabled": True}
    )
    if rejected:
        with pytest.raises(HTTPException, match="冲突"):
            await binding_api.update_rust_rcon_binding(
                parent_id, RustRconBindingUpdate(**changes), None
            )
        async with factory() as session:
            row = await session.get(RustRconBinding, parent_id)
            assert row.alias == "rcon1"
            assert not row.enabled
    else:
        saved = await binding_api.update_rust_rcon_binding(
            parent_id, RustRconBindingUpdate(**changes), None
        )
        assert saved.alias == "rcon2"
        assert saved.enabled
