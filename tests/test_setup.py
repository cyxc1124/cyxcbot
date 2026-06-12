"""Tests for one-time setup race protection."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import uuid
from unittest.mock import MagicMock

import nonebot
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_NONE_BOT_SQLITE = "sqlite+aiosqlite:///:memory:"
_DB_MODULE_NAMES = (
    "admin.services.setup_guard",
    "shared.db.models",
    "shared.db.base",
    "nonebot_plugin_orm",
)


def _ensure_real_db_modules() -> None:
    for name in _DB_MODULE_NAMES:
        module = sys.modules.get(name)
        if module is not None and isinstance(module, MagicMock):
            del sys.modules[name]

    os.environ["SQLALCHEMY_DATABASE_URL"] = _NONE_BOT_SQLITE
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=_NONE_BOT_SQLITE,
            alembic_startup_check=False,
        )

    if "nonebot_plugin_orm" not in sys.modules or isinstance(
        sys.modules["nonebot_plugin_orm"], MagicMock
    ):
        sys.modules.pop("nonebot_plugin_orm", None)
        nonebot.load_plugin("nonebot_plugin_orm")

    import shared.db.base
    import shared.db.models

    importlib.reload(shared.db.base)
    importlib.reload(shared.db.models)

    if "admin.services.setup_guard" in sys.modules:
        importlib.reload(sys.modules["admin.services.setup_guard"])


def _shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


@pytest.fixture(scope="module", autouse=True)
def _init_nonebot() -> None:
    _ensure_real_db_modules()


@pytest.fixture
async def session_factory():
    from shared.db.base import Model

    engine = create_async_engine(_shared_sqlite_url())
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _complete_setup(
    factory: async_sessionmaker[AsyncSession],
    username: str,
) -> str:
    from admin.auth.password import hash_password
    from admin.services.setup_guard import claim_initial_setup
    from shared.db.models import User

    async with factory() as session:
        async with session.begin():
            try:
                await claim_initial_setup(session)
            except HTTPException as exc:
                return str(exc.status_code)

            session.add(
                User(
                    username=username,
                    password_hash=hash_password("password123"),
                    is_admin=True,
                )
            )
            return "success"


@pytest.mark.asyncio
async def test_concurrent_initial_setup_allows_only_one_admin(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from shared.db.models import User

    results = await asyncio.gather(
        _complete_setup(session_factory, "admin_one"),
        _complete_setup(session_factory, "admin_two"),
    )

    assert sorted(results) == ["409", "success"]

    async with session_factory() as session:
        user_count = await session.scalar(select(func.count()).select_from(User))
    assert user_count == 1


@pytest.mark.asyncio
async def test_second_setup_attempt_returns_403(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await _complete_setup(session_factory, "admin")
    assert first == "success"

    second = await _complete_setup(session_factory, "other_admin")
    assert second == "403"
