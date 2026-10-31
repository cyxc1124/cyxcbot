"""Tests for Rust player store helpers."""

from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.db_test_helpers import ensure_real_db_modules

if "nonebot_plugin_orm" not in sys.modules:
    sys.modules["nonebot_plugin_orm"] = MagicMock(get_session=MagicMock())

from shared.rust_player.store import (
    TodayCheckInState,
    _ensure_steam_binding_available,
    needs_rcon_online_check,
)

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
async def rust_player_store(tmp_path):
    ensure_real_db_modules()
    import nonebot_plugin_orm

    from shared.db.base import Model

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'rust.db'}",
        poolclass=NullPool,
    )
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


@pytest.mark.asyncio
async def test_perform_check_in_offline_then_claim_bonus(
    rust_player_store, monkeypatch
) -> None:
    store, _factory = rust_player_store
    monkeypatch.setattr(store.random, "randint", lambda _min, _max: 5)

    offline = await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=False,
        can_claim_online_bonus=True,
    )
    assert offline.ok is True
    assert offline.base_points == 5
    assert offline.online_bonus == 0
    assert offline.total_points == 5

    pending = await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=False,
        can_claim_online_bonus=True,
    )
    assert pending.bonus_pending is True
    assert pending.total_points == 5

    claimed = await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=True,
        can_claim_online_bonus=True,
    )
    assert claimed.ok is True
    assert claimed.bonus_only is True
    assert claimed.online_bonus == 50
    assert claimed.total_points == 55

    done = await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=True,
        can_claim_online_bonus=True,
    )
    assert done.already_checked_in is True
    assert done.total_points == 55


@pytest.mark.asyncio
async def test_perform_check_in_online_awards_bonus_immediately(
    rust_player_store, monkeypatch
) -> None:
    store, _factory = rust_player_store
    monkeypatch.setattr(store.random, "randint", lambda _min, _max: 3)

    result = await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=True,
        can_claim_online_bonus=True,
    )
    assert result.ok is True
    assert result.base_points == 3
    assert result.online_bonus == 50
    assert result.total_points == 53


@pytest.mark.asyncio
async def test_perform_check_in_without_bonus_eligibility(
    rust_player_store, monkeypatch
) -> None:
    store, _factory = rust_player_store
    monkeypatch.setattr(store.random, "randint", lambda _min, _max: 4)

    first = await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=False,
        can_claim_online_bonus=False,
    )
    assert first.ok is True
    assert first.total_points == 4

    second = await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=True,
        can_claim_online_bonus=False,
    )
    assert second.already_checked_in is True
    assert second.bonus_pending is False


@pytest.mark.asyncio
async def test_concurrent_bonus_claim_is_atomic(rust_player_store, monkeypatch) -> None:
    store, _factory = rust_player_store
    monkeypatch.setattr(store.random, "randint", lambda _min, _max: 5)

    await store.perform_check_in(
        "10001",
        _TEST_USER,
        min_points=1,
        max_points=10,
        configured_online_bonus=50,
        is_online=False,
        can_claim_online_bonus=True,
    )

    results = await asyncio.gather(
        store.perform_check_in(
            "10001",
            _TEST_USER,
            min_points=1,
            max_points=10,
            configured_online_bonus=50,
            is_online=True,
            can_claim_online_bonus=True,
        ),
        store.perform_check_in(
            "10001",
            _TEST_USER,
            min_points=1,
            max_points=10,
            configured_online_bonus=50,
            is_online=True,
            can_claim_online_bonus=True,
        ),
    )

    bonus_claims = [result for result in results if result.ok and result.bonus_only]
    assert len(bonus_claims) == 1
    assert await store.get_group_points("10001", _TEST_USER) == 55


@pytest.mark.asyncio
async def test_credit_preserves_concurrent_shop_deduction(
    rust_player_store, monkeypatch
) -> None:
    from shared.db.models import RustPlayerPoints
    from shared.rust_player import shop_store

    store, factory = rust_player_store
    monkeypatch.setattr(shop_store, "get_session", factory)
    await store.set_group_points("10001", _TEST_USER, 100)

    async with factory() as session, session.begin():
        stale_balance = await session.get(
            RustPlayerPoints, {"group_id": "10001", "user_id": _TEST_USER}
        )
        assert stale_balance.points == 100
        assert await shop_store.deduct_group_points("10001", _TEST_USER, 30) == 70
        total = await store._add_points_in_session(session, "10001", _TEST_USER, 5)

    assert total == 75
    assert await store.get_group_points("10001", _TEST_USER) == 75


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["check_in", "steam_binding"])
async def test_reward_failure_rolls_back_record_and_balance(
    rust_player_store, monkeypatch, operation
) -> None:
    from shared.db.models import (
        RustCheckInRecord,
        RustSteamBindBonusAwarded,
        RustSteamBinding,
    )

    store, factory = rust_player_store
    add_points = store._add_points_in_session

    async def fail_after_credit(*args):
        await add_points(*args)
        raise RuntimeError("points write failed")

    async def award():
        if operation == "check_in":
            return await store.perform_check_in(
                "10001", _TEST_USER, min_points=5, max_points=5
            )
        return await store.create_steam_binding(
            _TEST_USER, _VALID_STEAM, group_id="10001", bind_bonus_points=5
        )

    monkeypatch.setattr(store, "_add_points_in_session", fail_after_credit)
    with pytest.raises(RuntimeError, match="points write failed"):
        await award()

    async with factory() as session:
        assert await session.get(RustSteamBinding, _TEST_USER) is None
        assert await session.get(RustSteamBindBonusAwarded, _TEST_USER) is None
        assert (
            await session.get(
                RustCheckInRecord,
                {
                    "group_id": "10001",
                    "user_id": _TEST_USER,
                    "check_in_date": store.today_check_in_date(),
                },
            )
            is None
        )
    assert await store.get_group_points("10001", _TEST_USER) == 0

    monkeypatch.setattr(store, "_add_points_in_session", add_points)
    result = await award()
    assert result.total_points == 5
    assert await store.get_group_points("10001", _TEST_USER) == 5


@pytest.mark.asyncio
async def test_concurrent_first_check_in_awards_once(rust_player_store) -> None:
    store, _factory = rust_player_store
    results = await asyncio.gather(
        *(
            store.perform_check_in("10001", _TEST_USER, min_points=5, max_points=5)
            for _ in range(2)
        )
    )
    assert sum(result.ok for result in results) == 1
    assert await store.get_group_points("10001", _TEST_USER) == 5


@pytest.mark.asyncio
async def test_concurrent_first_balance_credits_are_added(rust_player_store) -> None:
    store, factory = rust_player_store

    async def credit(delta):
        async with factory() as session, session.begin():
            return await store._add_points_in_session(
                session, "10001", _TEST_USER, delta
            )

    await asyncio.gather(credit(5), credit(7))
    assert await store.get_group_points("10001", _TEST_USER) == 12


@pytest.mark.asyncio
async def test_existing_sqlite_transaction_is_preserved(
    rust_player_store, tmp_path
) -> None:
    from shared.db.base import Model

    store, _factory = rust_player_store
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'modern.db'}",
        connect_args={"autocommit": False},
    )
    factory = async_sessionmaker(engine)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Model.metadata.create_all)
        async with factory() as session:
            with pytest.raises(RuntimeError, match="rollback"):
                async with session.begin():
                    await store._ensure_write_transaction(session)
                    await store._add_points_in_session(session, "10001", _TEST_USER, 5)
                    raise RuntimeError("rollback")
        async with factory() as session:
            assert await store._get_points_in_session(session, "10001", _TEST_USER) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_steam_binding_awards_first_bind_bonus(rust_player_store) -> None:
    store, _factory = rust_player_store

    result = await store.create_steam_binding(
        _TEST_USER,
        _VALID_STEAM,
        group_id="10001",
        bind_bonus_points=200,
    )
    assert result.steam_id == _VALID_STEAM
    assert result.bind_bonus_points == 200
    assert result.total_points == 200
    assert await store.get_group_points("10001", _TEST_USER) == 200


@pytest.mark.asyncio
async def test_create_steam_binding_skips_bonus_after_rebind(rust_player_store) -> None:
    store, _factory = rust_player_store

    first = await store.create_steam_binding(
        _TEST_USER,
        _VALID_STEAM,
        group_id="10001",
        bind_bonus_points=200,
    )
    assert first.bind_bonus_points == 200

    await store.delete_steam_binding(_TEST_USER)
    rebound = await store.create_steam_binding(
        _TEST_USER,
        "76561198000000001",
        group_id="10001",
        bind_bonus_points=200,
    )
    assert rebound.bind_bonus_points == 0
    assert await store.get_group_points("10001", _TEST_USER) == 200


@pytest.mark.asyncio
async def test_create_steam_binding_skips_bonus_when_steam_id_already_awarded(
    rust_player_store,
) -> None:
    store, _factory = rust_player_store
    other_user = "654321"
    other_steam = "76561198000000001"

    first = await store.create_steam_binding(
        _TEST_USER,
        _VALID_STEAM,
        group_id="10001",
        bind_bonus_points=200,
    )
    assert first.bind_bonus_points == 200

    await store.delete_steam_binding(_TEST_USER)
    second = await store.create_steam_binding(
        other_user,
        _VALID_STEAM,
        group_id="10001",
        bind_bonus_points=200,
    )
    assert second.bind_bonus_points == 0
    assert await store.get_group_points("10001", other_user) == 0

    await store.delete_steam_binding(other_user)
    third = await store.create_steam_binding(
        other_user,
        other_steam,
        group_id="10001",
        bind_bonus_points=200,
    )
    assert third.bind_bonus_points == 200
    assert await store.get_group_points("10001", other_user) == 200


@pytest.mark.asyncio
async def test_create_steam_binding_zero_bonus(rust_player_store) -> None:
    store, _factory = rust_player_store

    result = await store.create_steam_binding(
        _TEST_USER,
        _VALID_STEAM,
        group_id="10001",
        bind_bonus_points=0,
    )
    assert result.bind_bonus_points == 0
    assert result.total_points == 0


def test_needs_rcon_online_check() -> None:
    assert (
        needs_rcon_online_check(
            TodayCheckInState(checked_in=False), bonus_eligible=True
        )
        is True
    )
    assert (
        needs_rcon_online_check(
            TodayCheckInState(checked_in=True, online_bonus_earned=0),
            bonus_eligible=True,
        )
        is True
    )
    assert (
        needs_rcon_online_check(
            TodayCheckInState(checked_in=True, online_bonus_earned=50),
            bonus_eligible=True,
        )
        is False
    )
    assert (
        needs_rcon_online_check(
            TodayCheckInState(checked_in=True, online_bonus_earned=0),
            bonus_eligible=False,
        )
        is False
    )
