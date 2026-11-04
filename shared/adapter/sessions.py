"""Persist official QQ group/C2C sessions from gateway events."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Literal

from nonebot.message import event_preprocessor
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from shared.adapter.inbound import (
    group_id_of,
    is_official_c2c_event,
    is_official_group_event,
    user_id_of,
)
from shared.db.defaults import utcnow

if TYPE_CHECKING:
    from shared.db.models import OfficialQQSession

SessionKind = Literal["group", "c2c"]

# 同一会话的重复消息只需偶尔刷新 last_seen；每条入站消息都 upsert 会白白争 SQLite 写锁。
_REFRESH_INTERVAL_SECONDS = 600.0
_MAX_REMEMBERED = 4096
_recent_upserts: dict[str, tuple[SessionKind, str, float]] = {}


def _fallback_name(kind: SessionKind, openid: str) -> str:
    prefix = "官方群" if kind == "group" else "官方用户"
    return f"{prefix} {openid[:8]}"


def _event_display_name(event: Any, kind: SessionKind) -> str:
    for attr in ("group_name", "name"):
        value = getattr(event, attr, None)
        if value:
            return str(value)[:128]
    author = getattr(event, "author", None)
    if author is not None:
        for attr in ("username", "name"):
            value = getattr(author, attr, None)
            if value:
                return str(value)[:128]
    return ""


def _orm_session():
    from nonebot_plugin_orm import get_session

    return get_session()


def _session_model():
    from shared.db.models import OfficialQQSession

    return OfficialQQSession


async def upsert_session(openid: str, kind: SessionKind, name: str = "") -> None:
    oid = str(openid).strip()
    if not oid:
        return
    model = _session_model()
    async with _orm_session() as session:
        async with session.begin():
            dialect = session.get_bind(mapper=model).dialect.name
            insert = {
                "sqlite": sqlite_insert,
                "postgresql": postgresql_insert,
                "mysql": mysql_insert,
                "mariadb": mysql_insert,
            }[dialect]
            now = utcnow()
            updates = {"kind": kind, "last_seen": now}
            if name:
                updates["name"] = name[:128]
            # 守卫和缓存预处理器并行写入，由数据库唯一键保证跨进程原子更新。
            statement = insert(model).values(
                openid=oid,
                kind=kind,
                name=name[:128] or _fallback_name(kind, oid),
                last_seen=now,
            )
            if dialect in {"mysql", "mariadb"}:
                statement = statement.on_duplicate_key_update(**updates)
            else:
                statement = statement.on_conflict_do_update(
                    index_elements=[model.openid], set_=updates
                )
            await session.execute(statement)


def _recently_recorded(openid: str, kind: SessionKind, name: str) -> bool:
    last = _recent_upserts.get(openid.strip())
    if last is None:
        return False
    last_kind, last_name, at = last
    if last_kind != kind or (name and name != last_name):
        return False
    return time.monotonic() - at < _REFRESH_INTERVAL_SECONDS


async def _upsert_if_stale(openid: str, kind: SessionKind, name: str) -> None:
    oid = openid.strip()
    if _recently_recorded(oid, kind, name):
        return
    await upsert_session(oid, kind, name)
    if len(_recent_upserts) >= _MAX_REMEMBERED:
        _recent_upserts.clear()
    previous = _recent_upserts.get(oid)
    _recent_upserts[oid] = (
        kind,
        name or (previous[1] if previous else ""),
        time.monotonic(),
    )


async def delete_session(openid: str) -> None:
    oid = str(openid).strip()
    if not oid:
        return
    _recent_upserts.pop(oid, None)
    model = _session_model()
    async with _orm_session() as session:
        async with session.begin():
            row = await session.get(model, oid)
            if row:
                await session.delete(row)


async def list_sessions(kind: SessionKind | None = None) -> list[OfficialQQSession]:
    model = _session_model()
    async with _orm_session() as session:
        stmt = select(model)
        if kind:
            stmt = stmt.where(model.kind == kind)
        rows = (await session.scalars(stmt)).all()
        return list(rows)


def _event_type_name(event: Any) -> str:
    return type(event).__name__


async def remember_official_session(event: Any) -> None:
    """记录官方群/C2C。

    守卫和本函数都是事件预处理，NoneBot 会并行执行。守卫抛出忽略后会取消同组任务；
    写库若被取消，aiosqlite 会在回滚时打出 no active connection。
    """
    import anyio

    with anyio.CancelScope(shield=True):
        await _remember_official_session(event)


async def _remember_official_session(event: Any) -> None:
    name = _event_type_name(event)
    if name in {"GroupDelRobotEvent"}:
        openid = group_id_of(event) or str(getattr(event, "group_openid", "") or "")
        await delete_session(openid)
        return
    if name in {"FriendDelEvent"}:
        await delete_session(user_id_of(event))
        return
    if name in {"GroupAddRobotEvent"} or is_official_group_event(event):
        openid = group_id_of(event)
        if openid:
            label = _event_display_name(event, "group")
            await _upsert_if_stale(openid, "group", label)
        return
    if name in {"FriendAddEvent"} or is_official_c2c_event(event):
        openid = user_id_of(event)
        if openid:
            label = _event_display_name(event, "c2c")
            await _upsert_if_stale(openid, "c2c", label)


@event_preprocessor
async def cache_official_qq_session(event) -> None:
    await remember_official_session(event)


def session_rows_as_groups(rows: list[OfficialQQSession]) -> list[dict]:
    return [
        {
            "group_id": row.openid,
            "group_name": row.name,
            "member_count": None,
            "source": "official",
        }
        for row in rows
        if row.kind == "group"
    ]


def session_rows_as_friends(rows: list[OfficialQQSession]) -> list[dict]:
    return [
        {
            "user_id": row.openid,
            "nickname": row.name,
            "source": "official",
        }
        for row in rows
        if row.kind == "c2c"
    ]
