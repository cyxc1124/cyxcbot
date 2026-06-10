"""OneBot group list and message policy endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.groups import (
    GroupInfo,
    GroupListResponse,
    GroupMessagePolicyResponse,
    GroupMessagePolicyUpdateRequest,
)
from admin.schemas.status_check import (
    GroupStatusPolicyResponse,
    GroupStatusPolicyUpdateRequest,
    StatusCheckDisplayOptions,
)
from admin.services.onebot_bridge import get_group_list
from shared.config.service import get_config_service
from shared.group_policy import is_group_message_enabled_from_snapshot

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    dependencies=[RequireSetup],
)


@router.get("", response_model=GroupListResponse)
async def list_groups(_: AdminUser):
    groups = await get_group_list()
    return GroupListResponse(groups=[GroupInfo(**g) for g in groups])


@router.get("/message-policy", response_model=GroupMessagePolicyResponse)
async def get_message_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    groups = await get_group_list()
    return GroupMessagePolicyResponse(
        restrict=snap.message_group_restrict,
        enabled_group_ids=snap.message_enabled_group_ids,
        groups=[GroupInfo(**g) for g in groups],
    )


@router.put("/message-policy", response_model=GroupMessagePolicyResponse)
async def update_message_policy(
    body: GroupMessagePolicyUpdateRequest,
    _: AdminUser,
):
    svc = get_config_service()
    enabled_ids = [str(gid).strip() for gid in body.enabled_group_ids if str(gid).strip()]
    await svc.set_settings(
        {
            "message_group_restrict": str(body.restrict).lower(),
            "message_enabled_group_ids": json.dumps(enabled_ids, ensure_ascii=False),
        }
    )
    await svc.reload()

    snap = svc.get_snapshot()
    groups = await get_group_list()
    return GroupMessagePolicyResponse(
        restrict=snap.message_group_restrict,
        enabled_group_ids=snap.message_enabled_group_ids,
        groups=[GroupInfo(**g) for g in groups],
    )


def _status_display_options(snap) -> StatusCheckDisplayOptions:
    return StatusCheckDisplayOptions(
        show_detailed=snap.status_check_show_detailed,
        show_uptime=snap.status_check_show_uptime,
        show_memory=snap.status_check_show_memory,
    )


def _message_enabled_groups(snap, groups: list[dict]) -> list[dict]:
    return [
        group
        for group in groups
        if is_group_message_enabled_from_snapshot(str(group["group_id"]), snap)
    ]


def _ensure_group_message_enabled(group_id: str, snap) -> None:
    if not is_group_message_enabled_from_snapshot(group_id, snap):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该群未启用群消息，无法配置状态查询",
        )


def _filter_status_enabled_group_ids(enabled_ids: list[str], groups: list[dict]) -> list[str]:
    allowed = {str(group["group_id"]) for group in groups}
    return [gid for gid in enabled_ids if gid in allowed]


@router.get("/status-policy", response_model=GroupStatusPolicyResponse)
async def get_status_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    groups = _message_enabled_groups(snap, await get_group_list())
    return GroupStatusPolicyResponse(
        restrict=snap.status_check_group_restrict,
        enabled_group_ids=_filter_status_enabled_group_ids(
            snap.status_check_enabled_group_ids, groups
        ),
        groups=[GroupInfo(**g) for g in groups],
        display=_status_display_options(snap),
    )


@router.put("/status-policy", response_model=GroupStatusPolicyResponse)
async def update_status_policy(
    body: GroupStatusPolicyUpdateRequest,
    _: AdminUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    message_groups = _message_enabled_groups(snap, await get_group_list())
    enabled_ids = [
        str(gid).strip()
        for gid in body.enabled_group_ids
        if str(gid).strip()
    ]
    for group_id in enabled_ids:
        _ensure_group_message_enabled(group_id, snap)
    enabled_ids = _filter_status_enabled_group_ids(enabled_ids, message_groups)
    updates: dict[str, str] = {
        "status_check_group_restrict": str(body.restrict).lower(),
        "status_check_enabled_group_ids": json.dumps(enabled_ids, ensure_ascii=False),
    }
    if body.display is not None:
        updates["status_check_show_detailed"] = str(body.display.show_detailed).lower()
        updates["status_check_show_uptime"] = str(body.display.show_uptime).lower()
        updates["status_check_show_memory"] = str(body.display.show_memory).lower()

    await svc.set_settings(updates)
    await svc.reload()

    snap = svc.get_snapshot()
    groups = _message_enabled_groups(snap, await get_group_list())
    return GroupStatusPolicyResponse(
        restrict=snap.status_check_group_restrict,
        enabled_group_ids=_filter_status_enabled_group_ids(
            snap.status_check_enabled_group_ids, groups
        ),
        groups=[GroupInfo(**g) for g in groups],
        display=_status_display_options(snap),
    )
