"""Tests for one-time setup race protection."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.db_test_helpers import ensure_real_db_modules, shared_sqlite_url


@pytest.fixture(scope="module", autouse=True)
def _init_nonebot() -> None:
    ensure_real_db_modules()


@pytest.fixture
async def session_factory():
    from shared.db.base import Model

    engine = create_async_engine(shared_sqlite_url())
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
