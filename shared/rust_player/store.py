"""Database operations for Rust player points and Steam bindings."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from shared.config.rust_player import normalize_player_points
from shared.db.models import RustCheckInRecord, RustPlayerPoints, RustSteamBinding

_CHECKIN_TZ = ZoneInfo("Asia/Shanghai")


def today_check_in_date() -> str:
    return datetime.now(_CHECKIN_TZ).date().isoformat()


@dataclass(frozen=True)
class CheckInResult:
    ok: bool
    points_earned: int = 0
    total_points: int = 0
    already_checked_in: bool = False


async def _detach_binding(session, row: RustSteamBinding) -> RustSteamBinding:
    await session.refresh(row)
    session.expunge(row)
    return row


async def get_steam_binding(user_id: str) -> RustSteamBinding | None:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(RustSteamBinding, str(user_id).strip())
            if row is None:
                return None
            return await _detach_binding(session, row)


async def get_steam_binding_by_steam_id(steam_id: str) -> RustSteamBinding | None:
    async with get_session() as session:
        async with session.begin():
            row = await session.scalar(
                select(RustSteamBinding).where(RustSteamBinding.steam_id == steam_id)
            )
            if row is None:
                return None
            return await _detach_binding(session, row)


async def _ensure_steam_binding_available(session, user_id: str, steam_id: str) -> None:
    existing_user = await session.get(RustSteamBinding, user_id)
    if existing_user is not None:
        raise ValueError("你已绑定 SteamID，如需更换请联系管理员")
    existing_steam = await session.scalar(
        select(RustSteamBinding).where(RustSteamBinding.steam_id == steam_id)
    )
    if existing_steam is not None:
        raise ValueError("该 SteamID 已被其他 QQ 号绑定")


async def create_steam_binding(user_id: str, steam_id: str) -> None:
    user_id = str(user_id).strip()
    steam_id = str(steam_id).strip()
    async with get_session() as session:
        async with session.begin():
            await _ensure_steam_binding_available(session, user_id, steam_id)
            try:
                async with session.begin_nested():
                    session.add(RustSteamBinding(user_id=user_id, steam_id=steam_id))
                    await session.flush()
            except IntegrityError:
                await _ensure_steam_binding_available(session, user_id, steam_id)
                raise ValueError("绑定失败，请稍后重试") from None


async def delete_steam_binding(user_id: str) -> bool:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(RustSteamBinding, str(user_id).strip())
            if row is None:
                return False
            await session.delete(row)
            return True


async def get_group_points(group_id: str, user_id: str) -> int:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(
                RustPlayerPoints,
                {"group_id": str(group_id).strip(), "user_id": str(user_id).strip()},
            )
            return row.points if row is not None else 0


async def set_group_points(group_id: str, user_id: str, points: int) -> int:
    points = normalize_player_points(points)
    async with get_session() as session:
        async with session.begin():
            row = await session.get(
                RustPlayerPoints,
                {"group_id": str(group_id).strip(), "user_id": str(user_id).strip()},
            )
            if row is None:
                row = RustPlayerPoints(
                    group_id=str(group_id).strip(),
                    user_id=str(user_id).strip(),
                    points=points,
                )
                session.add(row)
            else:
                row.points = points
            return points


async def perform_check_in(
    group_id: str,
    user_id: str,
    *,
    min_points: int,
    max_points: int,
) -> CheckInResult:
    group_id = str(group_id).strip()
    user_id = str(user_id).strip()
    check_in_date = today_check_in_date()
    points_earned = random.randint(min_points, max_points)

    async with get_session() as session:
        async with session.begin():
            existing = await session.get(
                RustCheckInRecord,
                {
                    "group_id": group_id,
                    "user_id": user_id,
                    "check_in_date": check_in_date,
                },
            )
            if existing is not None:
                total = await _get_points_in_session(session, group_id, user_id)
                return CheckInResult(
                    ok=False,
                    total_points=total,
                    already_checked_in=True,
                )

            try:
                async with session.begin_nested():
                    session.add(
                        RustCheckInRecord(
                            group_id=group_id,
                            user_id=user_id,
                            check_in_date=check_in_date,
                            points_earned=points_earned,
                        )
                    )
                    await session.flush()
            except IntegrityError:
                total = await _get_points_in_session(session, group_id, user_id)
                return CheckInResult(
                    ok=False,
                    total_points=total,
                    already_checked_in=True,
                )
            total = await _add_points_in_session(
                session, group_id, user_id, points_earned
            )

    return CheckInResult(
        ok=True,
        points_earned=points_earned,
        total_points=total,
    )


async def _get_points_in_session(session, group_id: str, user_id: str) -> int:
    row = await session.get(
        RustPlayerPoints,
        {"group_id": group_id, "user_id": user_id},
    )
    return row.points if row is not None else 0


async def _add_points_in_session(
    session, group_id: str, user_id: str, delta: int
) -> int:
    row = await session.get(
        RustPlayerPoints,
        {"group_id": group_id, "user_id": user_id},
    )
    if row is None:
        row = RustPlayerPoints(group_id=group_id, user_id=user_id, points=delta)
        session.add(row)
    else:
        row.points += delta
    await session.flush()
    return row.points


async def list_player_overview() -> list[dict[str, object]]:
    async with get_session() as session:
        async with session.begin():
            points_rows = (
                await session.scalars(
                    select(RustPlayerPoints).order_by(RustPlayerPoints.group_id)
                )
            ).all()
            steam_rows = {
                row.user_id: row.steam_id
                for row in (await session.scalars(select(RustSteamBinding))).all()
            }
            items: list[dict[str, object]] = []
            seen_users: set[str] = set()
            for row in points_rows:
                seen_users.add(row.user_id)
                items.append(
                    {
                        "group_id": row.group_id,
                        "user_id": row.user_id,
                        "points": row.points,
                        "steam_id": steam_rows.get(row.user_id),
                    }
                )
            for user_id, steam_id in steam_rows.items():
                if user_id in seen_users:
                    continue
                items.append(
                    {
                        "group_id": None,
                        "user_id": user_id,
                        "points": 0,
                        "steam_id": steam_id,
                    }
                )
            return items
