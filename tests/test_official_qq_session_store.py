"""Official session writes stay atomic across concurrent event preprocessors."""

import asyncio
import importlib.util
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import nonebot.message
import pytest
from nonebot.adapters.qq import Bot as QQBot
from sqlalchemy import select
from sqlalchemy.dialects import mysql, postgresql
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.adapter import sessions
from shared.adapter.official_runtime import _bot_info
from tests.test_config_service_load_perf import _ensure_real_db_modules
from tests.test_official_qq_adapter import _official_event


@pytest.fixture
async def session_db(tmp_path, monkeypatch):
    _ensure_real_db_modules()
    from shared.db.models import OfficialQQSession

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sessions.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(OfficialQQSession.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(sessions, "_orm_session", factory)
    monkeypatch.setattr(sessions, "_session_model", lambda: OfficialQQSession)
    try:
        yield engine, factory, OfficialQQSession
    finally:
        await engine.dispose()


def _synchronize_missing_reads(engine, model, monkeypatch):
    barrier = asyncio.Barrier(2)

    class ConcurrentSession(AsyncSession):
        async def get(self, entity, ident, **kwargs):
            row = await super().get(entity, ident, **kwargs)
            if entity is model and row is None:
                # Reproduce both legacy SELECTs reading an absent row before INSERT.
                await barrier.wait()
            return row

    monkeypatch.setattr(
        sessions, "_orm_session", async_sessionmaker(engine, class_=ConcurrentSession)
    )


@pytest.mark.parametrize("kind", ["group", "c2c"])
async def test_concurrent_first_seen_session_is_one_row(session_db, monkeypatch, kind):
    engine, factory, model = session_db
    _synchronize_missing_reads(engine, model, monkeypatch)
    await asyncio.wait_for(
        asyncio.gather(
            *(sessions.upsert_session("new-openid", kind) for _ in range(8))
        ),
        timeout=5,
    )
    async with factory() as session:
        rows = (await session.scalars(select(model))).all()
    assert len(rows) == 1
    assert rows[0].kind == kind
    assert rows[0].name == sessions._fallback_name(kind, "new-openid")


async def test_updates_preserve_name_and_refresh_last_seen(session_db, monkeypatch):
    _, factory, model = session_db
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(minutes=1)
    third = second + timedelta(minutes=1)
    times = iter([first, second, third])
    monkeypatch.setattr(sessions, "utcnow", lambda: next(times))
    await sessions.upsert_session(" user-openid ", "c2c", "User")
    await sessions.upsert_session("user-openid", "group")
    async with factory() as session:
        row = await session.get(model, "user-openid")
        assert row.kind == "group"
        assert row.name == "User"
        assert row.last_seen.replace(tzinfo=timezone.utc) == second
    await sessions.upsert_session("user-openid", "group", "改" * 140)
    async with factory() as session:
        row = await session.get(model, "user-openid")
        assert row.name == "改" * 128
        assert row.last_seen.replace(tzinfo=timezone.utc) == third
    await sessions.delete_session("user-openid")
    assert await sessions.list_sessions() == []


async def test_blank_openid_skips_database(monkeypatch):
    database = MagicMock()
    monkeypatch.setattr(sessions, "_orm_session", database)
    await sessions.upsert_session("  ", "group")
    database.assert_not_called()


@pytest.mark.parametrize("scope", ["group", "c2c"])
async def test_first_message_survives_guard_and_cache_preprocessors(
    scope, session_db, monkeypatch
):
    engine, factory, model = session_db
    _synchronize_missing_reads(engine, model, monkeypatch)
    monkeypatch.setattr(nonebot.message, "_event_preprocessors", set())
    nonebot.message.event_preprocessor(sessions.cache_official_qq_session)
    name = f"_session_store_{scope}_guard"
    guard_path = (
        Path(__file__).resolve().parents[1]
        / "plugins"
        / ("group_guard" if scope == "group" else "private_guard")
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(name, guard_path)
    guard = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, guard)
    spec.loader.exec_module(guard)
    snapshot = SimpleNamespace(
        message_group_restrict=False,
        message_private_restrict=False,
        message_enabled_group_ids=[],
        message_enabled_user_ids=[],
    )
    monkeypatch.setattr(
        guard,
        "get_config_service",
        lambda: SimpleNamespace(get_snapshot=lambda: snapshot),
    )
    bot = QQBot(MagicMock(), "test-app", _bot_info("test-app", "test-secret", False))
    assert len(nonebot.message._event_preprocessors) == 2
    proceed = await asyncio.wait_for(
        nonebot.message._apply_event_preprocessors(
            bot, _official_event(scope), {}, show_log=False
        ),
        timeout=5,
    )
    assert proceed is True
    async with factory() as session:
        rows = (await session.scalars(select(model))).all()
    assert len(rows) == 1
    assert rows[0].openid == ("test-group" if scope == "group" else "test-user")


@pytest.mark.parametrize("name", ["", "User"])
@pytest.mark.parametrize(
    "dialect, conflict_clause",
    [
        pytest.param(
            postgresql.dialect(),
            "ON CONFLICT (openid) DO UPDATE SET ",
            id="postgresql",
        ),
        pytest.param(
            mysql.aiomysql.dialect(),
            "ON DUPLICATE KEY UPDATE ",
            id="mysql-aiomysql",
        ),
        pytest.param(
            mysql.asyncmy.dialect(),
            "ON DUPLICATE KEY UPDATE ",
            id="mysql-asyncmy",
        ),
        pytest.param(MariaDBDialect(), "ON DUPLICATE KEY UPDATE ", id="mariadb"),
    ],
)
async def test_upsert_compiles_with_correct_name_update(
    session_db, monkeypatch, name, dialect, conflict_clause
):
    _, _, model = session_db
    session = MagicMock(spec=AsyncSession)
    session.__aenter__.return_value = session
    session.get_bind.return_value = SimpleNamespace(dialect=dialect)
    session.execute = AsyncMock()
    monkeypatch.setattr(sessions, "_orm_session", lambda: session)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(sessions, "utcnow", lambda: now)
    await sessions.upsert_session("openid", "c2c", name)
    statement = session.execute.await_args.args[0]
    bound = statement.compile(dialect=dialect)
    assert bound.params["openid"] == "openid"
    assert bound.params["kind"] == "c2c"
    assert bound.params["last_seen"] == now
    stored_name = name or sessions._fallback_name("c2c", "openid")
    assert bound.params["name"] == stored_name
    compiled = statement.compile(dialect=type(dialect)(paramstyle="named"))
    insert_sql, separator, update_sql = str(compiled).partition(conflict_clause)
    assert separator
    expected_updates = {"kind": "c2c", "last_seen": now}
    if name:
        expected_updates["name"] = name
    update_bindings = re.findall(r"(\w+) = :(\w+)", update_sql)
    assert {
        column: compiled.params[parameter] for column, parameter in update_bindings
    } == expected_updates
    assert "VALUES (:openid, :kind, :name, :last_seen)" in insert_sql
    session.get_bind.assert_called_once_with(mapper=model)
