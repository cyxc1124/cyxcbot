"""Database operations for Rust player points and Steam bindings."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot_plugin_orm import get_session
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from shared.config.rust_player import normalize_player_points
from shared.db.models import RustCheckInRecord, RustPlayerPoints, RustSteamBinding

_CHECKIN_TZ = ZoneInfo("Asia/Shanghai")


def today_check_in_date() -> str:
    return datetime.now(_CHECKIN_TZ).date().isoformat()


@dataclass(frozen=True)
class CheckInResult:
    ok: bool
    base_points: int = 0
    online_bonus: int = 0
    total_points: int = 0
    already_checked_in: bool = False
    bonus_pending: bool = False
    bonus_only: bool = False

    @property
    def points_earned(self) -> int:
        return self.base_points + self.online_bonus


@dataclass(frozen=True)
class TodayCheckInState:
    checked_in: bool
    online_bonus_earned: int = 0


def needs_rcon_online_check(state: TodayCheckInState, *, bonus_eligible: bool) -> bool:
    """Whether check-in should query RCON ``status`` for online bonus."""
    if not bonus_eligible:
        return False
    if not state.checked_in:
        return True
    return state.online_bonus_earned == 0


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


async def get_today_check_in_state(group_id: str, user_id: str) -> TodayCheckInState:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(
                RustCheckInRecord,
                {
                    "group_id": str(group_id).strip(),
                    "user_id": str(user_id).strip(),
                    "check_in_date": today_check_in_date(),
                },
            )
            if row is None:
                return TodayCheckInState(checked_in=False)
            return TodayCheckInState(
                checked_in=True,
                online_bonus_earned=row.online_bonus_earned,
            )


async def perform_check_in(
    group_id: str,
    user_id: str,
    *,
    min_points: int,
    max_points: int,
    configured_online_bonus: int = 0,
    is_online: bool = False,
    can_claim_online_bonus: bool = False,
) -> CheckInResult:
    group_id = str(group_id).strip()
    user_id = str(user_id).strip()
    check_in_date = today_check_in_date()
    configured_online_bonus = max(0, int(configured_online_bonus))
    bonus_eligible = can_claim_online_bonus and configured_online_bonus > 0

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
            if existing is None:
                base_points = random.randint(min_points, max_points)
                online_bonus = (
                    configured_online_bonus if bonus_eligible and is_online else 0
                )
                points_earned = base_points + online_bonus
                try:
                    async with session.begin_nested():
                        session.add(
                            RustCheckInRecord(
                                group_id=group_id,
                                user_id=user_id,
                                check_in_date=check_in_date,
                                points_earned=points_earned,
                                online_bonus_earned=online_bonus,
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
                    base_points=base_points,
                    online_bonus=online_bonus,
                    total_points=total,
                )

            total = await _get_points_in_session(session, group_id, user_id)
            online_bonus_earned = existing.online_bonus_earned
            session.expunge(existing)
            if online_bonus_earned > 0 or not bonus_eligible:
                return CheckInResult(
                    ok=False,
                    total_points=total,
                    already_checked_in=True,
                )
            if not is_online:
                return CheckInResult(
                    ok=False,
                    total_points=total,
                    bonus_pending=True,
                )

            online_bonus = configured_online_bonus
            update_result = await session.execute(
                update(RustCheckInRecord)
                .where(
                    RustCheckInRecord.group_id == group_id,
                    RustCheckInRecord.user_id == user_id,
                    RustCheckInRecord.check_in_date == check_in_date,
                    RustCheckInRecord.online_bonus_earned == 0,
                )
                .values(
                    online_bonus_earned=online_bonus,
                    points_earned=RustCheckInRecord.points_earned + online_bonus,
                )
            )
            if update_result.rowcount != 1:
                total = await _get_points_in_session(session, group_id, user_id)
                return CheckInResult(
                    ok=False,
                    total_points=total,
                    already_checked_in=True,
                )
            session.expire_all()
            points_result = await session.execute(
                update(RustPlayerPoints)
                .where(
                    RustPlayerPoints.group_id == group_id,
                    RustPlayerPoints.user_id == user_id,
                )
                .values(points=RustPlayerPoints.points + online_bonus)
            )
            if points_result.rowcount != 1:
                session.add(
                    RustPlayerPoints(
                        group_id=group_id,
                        user_id=user_id,
                        points=online_bonus,
                    )
                )
                await session.flush()
            total = await _get_points_in_session(session, group_id, user_id)
            return CheckInResult(
                ok=True,
                online_bonus=online_bonus,
                total_points=total,
                bonus_only=True,
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
