"""Tests for Rust player store helpers."""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

import nonebot
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if "nonebot_plugin_orm" not in sys.modules:
    sys.modules["nonebot_plugin_orm"] = MagicMock(get_session=MagicMock())

from shared.rust_player.store import _ensure_steam_binding_available

_VALID_STEAM = "76561198000000000"


def _shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


@pytest.fixture
def rust_player_store_modules():
    for name in ("shared.rust_player.store", "shared.db.models", "shared.db.base"):
        module = sys.modules.get(name)
        if module is not None and isinstance(module, MagicMock):
            del sys.modules[name]

    db_url = _shared_sqlite_url()
    os.environ["SQLALCHEMY_DATABASE_URL"] = db_url
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=db_url,
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

    import shared.rust_player.store as store

    importlib.reload(store)
    return store, db_url


@pytest.fixture
async def rust_player_session_factory(rust_player_store_modules):
    from shared.db.base import Model

    _, db_url = rust_player_store_modules
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=True)
    import nonebot_plugin_orm

    original = nonebot_plugin_orm.get_session
    nonebot_plugin_orm.get_session = lambda: factory()
    try:
        yield factory
    finally:
        nonebot_plugin_orm.get_session = original
        await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_steam_binding_available_rejects_bound_user() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock())

    with pytest.raises(ValueError, match="你已绑定 SteamID"):
        await _ensure_steam_binding_available(session, "123", _VALID_STEAM)


@pytest.mark.asyncio
async def test_get_steam_binding_returns_usable_row_after_session_close(
    rust_player_store_modules,
    rust_player_session_factory,
) -> None:
    from shared.db.models import RustSteamBinding

    store, _ = rust_player_store_modules
    factory = rust_player_session_factory
    async with factory() as session:
        async with session.begin():
            session.add(
                RustSteamBinding(user_id="123456", steam_id=_VALID_STEAM)
            )

    binding = await store.get_steam_binding("123456")
    assert binding is not None
    assert binding.steam_id == _VALID_STEAM
