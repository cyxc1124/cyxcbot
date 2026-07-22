"""Tests for Rust player store helpers."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.db_test_helpers import ensure_real_db_modules, shared_sqlite_url

if "nonebot_plugin_orm" not in sys.modules:
    sys.modules["nonebot_plugin_orm"] = MagicMock(get_session=MagicMock())

from shared.rust_player.store import _ensure_steam_binding_available

_VALID_STEAM = "76561198000000000"
_TEST_USER = "123456"


async def _seed_steam_binding(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    steam_id: str,
) -> None:
    from shared.db.models import RustSteamBinding

    async with factory() as session:
        async with session.begin():
            session.add(RustSteamBinding(user_id=user_id, steam_id=steam_id))


@pytest.fixture
async def rust_player_store():
    ensure_real_db_modules()
    import nonebot_plugin_orm

    from shared.db.base import Model

    engine = create_async_engine(shared_sqlite_url())
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=True)
    original_get_session = nonebot_plugin_orm.get_session
    nonebot_plugin_orm.get_session = lambda: factory()

    import shared.rust_player.store as store

    importlib.reload(store)
    try:
        yield store, factory
    finally:
        nonebot_plugin_orm.get_session = original_get_session
        importlib.reload(store)
        await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_steam_binding_available_rejects_bound_user() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock())

    with pytest.raises(ValueError, match="你已绑定 SteamID"):
        await _ensure_steam_binding_available(session, "123", _VALID_STEAM)


@pytest.mark.asyncio
async def test_get_steam_binding_returns_usable_row_after_session_close(
    rust_player_store,
) -> None:
    store, factory = rust_player_store
    await _seed_steam_binding(factory, user_id=_TEST_USER, steam_id=_VALID_STEAM)

    binding = await store.get_steam_binding(_TEST_USER)
    assert binding is not None
    assert binding.steam_id == _VALID_STEAM


@pytest.mark.asyncio
async def test_get_steam_binding_by_steam_id_returns_usable_row_after_session_close(
    rust_player_store,
) -> None:
    store, factory = rust_player_store
    await _seed_steam_binding(factory, user_id=_TEST_USER, steam_id=_VALID_STEAM)

    binding = await store.get_steam_binding_by_steam_id(_VALID_STEAM)
    assert binding is not None
    assert binding.user_id == _TEST_USER
    assert binding.steam_id == _VALID_STEAM
