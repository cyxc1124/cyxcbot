"""Status check (/status) scope policy for groups and friends."""

from __future__ import annotations


def is_status_check_enabled_for_group(
    group_id: str,
    *,
    restrict: bool,
    enabled_group_ids: list[str],
) -> bool:
    if not restrict:
        return True
    gid = str(group_id).strip()
    enabled = {str(item).strip() for item in enabled_group_ids if str(item).strip()}
    return gid in enabled


def is_status_check_enabled_for_user(
    user_id: str,
    *,
    restrict: bool,
    enabled_user_ids: list[str],
) -> bool:
    if not restrict:
        return True
    uid = str(user_id).strip()
    enabled = {str(item).strip() for item in enabled_user_ids if str(item).strip()}
    return uid in enabled


def is_status_check_enabled_for_group_from_snapshot(group_id: str, snapshot) -> bool:
    return is_status_check_enabled_for_group(
        group_id,
        restrict=snapshot.status_check_group_restrict,
        enabled_group_ids=snapshot.status_check_enabled_group_ids,
    )


def is_status_check_enabled_for_user_from_snapshot(user_id: str, snapshot) -> bool:
    return is_status_check_enabled_for_user(
        user_id,
        restrict=snapshot.status_check_private_restrict,
        enabled_user_ids=snapshot.status_check_enabled_user_ids,
    )


def is_status_check_allowed_from_snapshot(
    user_id: str, snapshot, *, group_id: str | None = None, is_private: bool = False
) -> bool:
    uid = str(user_id).strip()
    if not uid:
        return False
    allowed_users = {
        str(item).strip()
        for item in snapshot.status_check_allowed_qq
        if str(item).strip()
    }
    if uid in allowed_users:
        return True
    gid = str(group_id).strip() if group_id is not None else ""
    if gid:
        return is_status_check_enabled_for_group_from_snapshot(gid, snapshot)
    return is_private and is_status_check_enabled_for_user_from_snapshot(
        user_id, snapshot
    )


async def is_status_check_allowed(bot, event, snapshot) -> bool:
    from nonebot.log import logger
    from nonebot.permission import SUPERUSER

    from shared.adapter.inbound import (
        group_id_of,
        is_group_event,
        is_private_event,
        user_id_of,
    )

    try:
        if await SUPERUSER(bot, event):
            return True
    except Exception:
        logger.debug("适配器事件无法按超级用户判定，改走状态查询白名单")
    return is_status_check_allowed_from_snapshot(
        user_id_of(event),
        snapshot,
        group_id=group_id_of(event) if is_group_event(event) else None,
        is_private=is_private_event(event),
    )
