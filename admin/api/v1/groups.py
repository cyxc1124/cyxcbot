"""OneBot group list and message policy endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.group_special_title import (
    GroupSpecialTitlePolicyResponse,
    GroupSpecialTitlePolicyUpdateRequest,
)
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
from admin.services.onebot_bridge import (
    get_group_list,
    get_group_list_with_availability,
    get_group_list_with_status,
)
from shared.config.service import get_config_service
from shared.group_policy import is_group_message_enabled_from_snapshot
from shared.group_special_title_policy import (
    filter_enabled_group_ids_to_visible_groups,
    special_title_policy_group_list_available,
)

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    dependencies=[RequireSetup],
)


def _group_list_available(status: str) -> bool:
    return status == "ok"


async def _ensure_group_list_complete_for_mutation() -> None:
    _, fetch_status = await get_group_list_with_status()
    if fetch_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="群列表不完整，暂不可修改策略",
        )


@router.get("", response_model=GroupListResponse)
async def list_groups(_: AdminUser):
    groups = await get_group_list()
    return GroupListResponse(groups=[GroupInfo(**g) for g in groups])


@router.get("/message-policy", response_model=GroupMessagePolicyResponse)
async def get_message_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    groups, fetch_status = await get_group_list_with_status()
    available = _group_list_available(fetch_status)
    return GroupMessagePolicyResponse(
        restrict=snap.message_group_restrict,
        enabled_group_ids=snap.message_enabled_group_ids,
        groups=[] if fetch_status == "offline" else [GroupInfo(**g) for g in groups],
        group_list_available=available,
    )


@router.put("/message-policy", response_model=GroupMessagePolicyResponse)
async def update_message_policy(
    body: GroupMessagePolicyUpdateRequest,
    _: AdminUser,
):
    await _ensure_group_list_complete_for_mutation()
    svc = get_config_service()
    enabled_ids = [
        str(gid).strip() for gid in body.enabled_group_ids if str(gid).strip()
    ]
    await svc.set_settings(
        {
            "message_group_restrict": str(body.restrict).lower(),
            "message_enabled_group_ids": json.dumps(enabled_ids, ensure_ascii=False),
        }
    )
    await svc.reload()

    snap = svc.get_snapshot()
    groups, fetch_status = await get_group_list_with_status()
    return GroupMessagePolicyResponse(
        restrict=snap.message_group_restrict,
        enabled_group_ids=snap.message_enabled_group_ids,
        groups=[] if fetch_status == "offline" else [GroupInfo(**g) for g in groups],
        group_list_available=_group_list_available(fetch_status),
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


def _ensure_group_message_enabled_for_special_title(group_id: str, snap) -> None:
    if not is_group_message_enabled_from_snapshot(group_id, snap):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该群未启用群消息，无法配置群头衔",
        )


def _normalized_group_ids(group_ids: list[str]) -> list[str]:
    return sorted({str(gid).strip() for gid in group_ids if str(gid).strip()})


def _special_title_policy_response(
    snap,
    groups: list[dict],
    *,
    group_list_available: bool,
) -> GroupSpecialTitlePolicyResponse:
    return GroupSpecialTitlePolicyResponse(
        restrict=snap.group_special_title_restrict,
        enabled_group_ids=filter_enabled_group_ids_to_visible_groups(
            snap.group_special_title_enabled_group_ids,
            groups,
            group_list_available=group_list_available,
        ),
        groups=[GroupInfo(**g) for g in groups],
        daily_limit=snap.group_special_title_daily_limit,
        group_list_available=group_list_available,
    )


def _filter_status_enabled_group_ids(
    enabled_ids: list[str], groups: list[dict]
) -> list[str]:
    allowed = {str(group["group_id"]) for group in groups}
    return [gid for gid in enabled_ids if gid in allowed]


def _status_policy_response(
    snap, groups: list[dict], *, group_list_available: bool
) -> GroupStatusPolicyResponse:
    return GroupStatusPolicyResponse(
        restrict=snap.status_check_group_restrict,
        enabled_group_ids=_filter_status_enabled_group_ids(
            snap.status_check_enabled_group_ids, groups
        ),
        groups=[GroupInfo(**g) for g in groups],
        display=_status_display_options(snap),
        group_list_available=group_list_available,
    )


@router.get("/status-policy", response_model=GroupStatusPolicyResponse)
async def get_status_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    raw_groups, fetch_status = await get_group_list_with_status()
    available = _group_list_available(fetch_status)
    groups = (
        [] if fetch_status == "offline" else _message_enabled_groups(snap, raw_groups)
    )
    return _status_policy_response(snap, groups, group_list_available=available)


@router.put("/status-policy", response_model=GroupStatusPolicyResponse)
async def update_status_policy(
    body: GroupStatusPolicyUpdateRequest,
    _: AdminUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    raw_groups, fetch_status = await get_group_list_with_status()
    available = _group_list_available(fetch_status)
    message_groups = (
        [] if fetch_status == "offline" else _message_enabled_groups(snap, raw_groups)
    )
    body_enabled_ids = [
        str(gid).strip() for gid in body.enabled_group_ids if str(gid).strip()
    ]

    if not available:
        whitelist_changed = body.restrict != snap.status_check_group_restrict or (
            _normalized_group_ids(body_enabled_ids)
            != _normalized_group_ids(snap.status_check_enabled_group_ids)
        )
        if whitelist_changed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="群列表不完整，暂不可修改状态查询白名单",
            )
        enabled_ids = list(snap.status_check_enabled_group_ids)
        restrict = snap.status_check_group_restrict
    else:
        enabled_ids = body_enabled_ids
        restrict = body.restrict
        for group_id in enabled_ids:
            _ensure_group_message_enabled(group_id, snap)
        enabled_ids = _filter_status_enabled_group_ids(enabled_ids, message_groups)

    updates: dict[str, str] = {
        "status_check_group_restrict": str(restrict).lower(),
        "status_check_enabled_group_ids": json.dumps(enabled_ids, ensure_ascii=False),
    }
    if body.display is not None:
        updates["status_check_show_detailed"] = str(body.display.show_detailed).lower()
        updates["status_check_show_uptime"] = str(body.display.show_uptime).lower()
        updates["status_check_show_memory"] = str(body.display.show_memory).lower()

    await svc.set_settings(updates)
    await svc.reload()

    snap = svc.get_snapshot()
    raw_groups, fetch_status = await get_group_list_with_status()
    available = _group_list_available(fetch_status)
    groups = (
        [] if fetch_status == "offline" else _message_enabled_groups(snap, raw_groups)
    )
    return _status_policy_response(snap, groups, group_list_available=available)


@router.get("/special-title-policy", response_model=GroupSpecialTitlePolicyResponse)
async def get_special_title_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    raw_groups, fetch_available = await get_group_list_with_availability()
    group_list_available = special_title_policy_group_list_available(
        fetch_available, raw_groups, snap
    )
    groups = _message_enabled_groups(snap, raw_groups)
    return _special_title_policy_response(
        snap,
        groups,
        group_list_available=group_list_available,
    )


@router.put("/special-title-policy", response_model=GroupSpecialTitlePolicyResponse)
async def update_special_title_policy(
    body: GroupSpecialTitlePolicyUpdateRequest,
    _: AdminUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    raw_groups, fetch_available = await get_group_list_with_availability()
    group_list_available = special_title_policy_group_list_available(
        fetch_available, raw_groups, snap
    )
    message_groups = _message_enabled_groups(snap, raw_groups)
    body_enabled_ids = [
        str(gid).strip() for gid in body.enabled_group_ids if str(gid).strip()
    ]

    if not group_list_available:
        whitelist_changed = body.restrict != snap.group_special_title_restrict or (
            _normalized_group_ids(body_enabled_ids)
            != _normalized_group_ids(snap.group_special_title_enabled_group_ids)
        )
        if whitelist_changed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="群列表不完整，暂不可修改群头衔白名单",
            )
        enabled_ids = list(snap.group_special_title_enabled_group_ids)
        restrict = snap.group_special_title_restrict
    else:
        enabled_ids = body_enabled_ids
        restrict = body.restrict
        for group_id in enabled_ids:
            _ensure_group_message_enabled_for_special_title(group_id, snap)
        enabled_ids = filter_enabled_group_ids_to_visible_groups(
            enabled_ids,
            message_groups,
            group_list_available=True,
        )

    updates: dict[str, str] = {
        "group_special_title_restrict": str(restrict).lower(),
        "group_special_title_enabled_group_ids": json.dumps(
            enabled_ids, ensure_ascii=False
        ),
    }
    if body.daily_limit is not None:
        updates["group_special_title_daily_limit"] = str(body.daily_limit)

    await svc.set_settings(updates)
    await svc.reload()

    snap = svc.get_snapshot()
    raw_groups, fetch_available = await get_group_list_with_availability()
    group_list_available = special_title_policy_group_list_available(
        fetch_available, raw_groups, snap
    )
    groups = _message_enabled_groups(snap, raw_groups)
    return _special_title_policy_response(
        snap,
        groups,
        group_list_available=group_list_available,
    )
