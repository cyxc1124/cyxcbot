"""Daily usage tracking for group special title commands."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot_plugin_orm import get_session
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from shared.db.models import GroupSpecialTitleUsage

_USAGE_TZ = ZoneInfo("Asia/Shanghai")


def today_usage_date() -> str:
    return datetime.now(_USAGE_TZ).date().isoformat()


def _usage_pk(group_id: str, user_id: str, usage_date: str) -> dict[str, str]:
    return {
        "group_id": group_id,
        "user_id": user_id,
        "usage_date": usage_date,
    }


async def _increment_if_under_limit(
    session,
    *,
    group_id: str,
    user_id: str,
    usage_date: str,
    daily_limit: int,
) -> bool:
    result = await session.execute(
        update(GroupSpecialTitleUsage)
        .where(
            GroupSpecialTitleUsage.group_id == group_id,
            GroupSpecialTitleUsage.user_id == user_id,
            GroupSpecialTitleUsage.usage_date == usage_date,
            GroupSpecialTitleUsage.count < daily_limit,
        )
        .values(count=GroupSpecialTitleUsage.count + 1)
    )
    return result.rowcount == 1


def _upsert_consume_stmt(
    dialect_name: str,
    *,
    group_id: str,
    user_id: str,
    usage_date: str,
    daily_limit: int,
):
    values = {
        "group_id": group_id,
        "user_id": user_id,
        "usage_date": usage_date,
        "count": 1,
    }
    if dialect_name == "sqlite":
        insert_stmt = sqlite_insert(GroupSpecialTitleUsage).values(**values)
    elif dialect_name == "postgresql":
        insert_stmt = pg_insert(GroupSpecialTitleUsage).values(**values)
    else:
        return None

    return insert_stmt.on_conflict_do_update(
        index_elements=["group_id", "user_id", "usage_date"],
        set_={"count": GroupSpecialTitleUsage.count + 1},
        where=GroupSpecialTitleUsage.count < daily_limit,
    )


async def _consume_with_locked_increment(
    session,
    *,
    group_id: str,
    user_id: str,
    usage_date: str,
    daily_limit: int,
) -> bool:
    if await _increment_if_under_limit(
        session,
        group_id=group_id,
        user_id=user_id,
        usage_date=usage_date,
        daily_limit=daily_limit,
    ):
        return True

    row = await session.get(
        GroupSpecialTitleUsage,
        _usage_pk(group_id, user_id, usage_date),
        with_for_update=True,
    )
    if row is not None:
        return False

    session.add(
        GroupSpecialTitleUsage(
            group_id=group_id,
            user_id=user_id,
            usage_date=usage_date,
            count=1,
        )
    )
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        return await _increment_if_under_limit(
            session,
            group_id=group_id,
            user_id=user_id,
            usage_date=usage_date,
            daily_limit=daily_limit,
        )
    return True


async def try_consume_daily_quota(
    group_id: str,
    user_id: str,
    daily_limit: int,
) -> bool:
    """Atomically reserve one daily usage slot; False when limit reached."""
    if daily_limit <= 0:
        return True

    usage_date = today_usage_date()
    async with get_session() as session:
        async with session.begin():
            upsert_stmt = _upsert_consume_stmt(
                session.bind.dialect.name,
                group_id=group_id,
                user_id=user_id,
                usage_date=usage_date,
                daily_limit=daily_limit,
            )
            if upsert_stmt is not None:
                result = await session.execute(upsert_stmt)
                return result.rowcount == 1

            return await _consume_with_locked_increment(
                session,
                group_id=group_id,
                user_id=user_id,
                usage_date=usage_date,
                daily_limit=daily_limit,
            )


async def release_daily_quota(group_id: str, user_id: str) -> None:
    """Return one reserved slot when the title API call fails."""
    usage_date = today_usage_date()
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                update(GroupSpecialTitleUsage)
                .where(
                    GroupSpecialTitleUsage.group_id == group_id,
                    GroupSpecialTitleUsage.user_id == user_id,
                    GroupSpecialTitleUsage.usage_date == usage_date,
                    GroupSpecialTitleUsage.count > 0,
                )
                .values(count=GroupSpecialTitleUsage.count - 1)
            )
