"""Audit and system event writers."""

from __future__ import annotations

from typing import Optional

from nonebot_plugin_orm import get_session

from shared.db.models import AuditLog, SystemEvent


async def write_audit(
    action: str,
    *,
    actor_user_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
) -> AuditLog:
    session = get_session()
    async with session.begin():
        entry = AuditLog(
            action=action,
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            ip_address=ip_address,
            details=details,
        )
        session.add(entry)
        await session.flush()
        return entry


async def write_system_event(
    event_type: str,
    message: str,
    *,
    details: Optional[str] = None,
) -> SystemEvent:
    session = get_session()
    async with session.begin():
        entry = SystemEvent(
            event_type=event_type,
            message=message,
            details=details,
        )
        session.add(entry)
        await session.flush()
        return entry
