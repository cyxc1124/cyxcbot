"""Retention cleanup for audit logs and system events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler
from sqlalchemy import delete

from nonebot_plugin_orm import get_session

from shared.config.service import get_config_service
from shared.db.models import AuditLog, SystemEvent


async def cleanup_old_records() -> None:
    """Delete audit logs and system events older than retention period."""
    snap = get_config_service().get_snapshot()
    audit_days = snap.audit_log_retention_days
    event_days = snap.event_retention_days
    now = datetime.now(timezone.utc)

    session = get_session()
    async with session.begin():
        audit_removed = 0
        event_removed = 0

        if audit_days > 0:
            audit_cutoff = now - timedelta(days=audit_days)
            audit_result = await session.execute(
                delete(AuditLog).where(AuditLog.created_at < audit_cutoff)
            )
            audit_removed = audit_result.rowcount or 0

        if event_days > 0:
            event_cutoff = now - timedelta(days=event_days)
            event_result = await session.execute(
                delete(SystemEvent).where(SystemEvent.created_at < event_cutoff)
            )
            event_removed = event_result.rowcount or 0

    logger.info(
        f"Audit cleanup: removed {audit_removed} audit logs, "
        f"{event_removed} system events "
        f"(retention: audit={audit_days}d, events={event_days}d)"
    )


def register_cleanup_job() -> None:
    """Register daily cleanup job at 03:00."""
    scheduler.add_job(
        cleanup_old_records,
        "cron",
        hour=3,
        minute=0,
        id="audit_retention_cleanup",
        replace_existing=True,
    )
    logger.info("Audit retention cleanup job registered (daily 03:00)")
