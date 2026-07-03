"""Daily usage tracking for group special title commands."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot_plugin_orm import get_session

from shared.db.models import GroupSpecialTitleUsage

_USAGE_TZ = ZoneInfo("Asia/Shanghai")


def today_usage_date() -> str:
    return datetime.now(_USAGE_TZ).date().isoformat()


async def get_today_usage(group_id: str, user_id: str) -> int:
    session = get_session()
    async with session.begin():
        row = await session.get(
            GroupSpecialTitleUsage,
            {
                "group_id": group_id,
                "user_id": user_id,
                "usage_date": today_usage_date(),
            },
        )
        return row.count if row else 0


async def record_successful_set(group_id: str, user_id: str) -> int:
    usage_date = today_usage_date()
    session = get_session()
    async with session.begin():
        row = await session.get(
            GroupSpecialTitleUsage,
            {
                "group_id": group_id,
                "user_id": user_id,
                "usage_date": usage_date,
            },
        )
        if row:
            row.count += 1
        else:
            row = GroupSpecialTitleUsage(
                group_id=group_id,
                user_id=user_id,
                usage_date=usage_date,
                count=1,
            )
            session.add(row)
        return row.count
