"""OneBot friend list and private message policy endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.private import (
    FriendInfo,
    FriendListResponse,
    PrivateMessagePolicyResponse,
    PrivateMessagePolicyUpdateRequest,
)
from admin.schemas.status_check import (
    PrivateStatusPolicyResponse,
    PrivateStatusPolicyUpdateRequest,
    StatusCheckDisplayOptions,
)
from admin.services.onebot_bridge import (
    get_friend_list,
    get_friend_list_with_availability,
    invalidate_user_list_cache,
)
from shared.config.service import get_config_service
from shared.private_policy import (
    filter_enabled_user_ids_to_visible_users,
    is_private_message_enabled_from_snapshot,
)

router = APIRouter(
    prefix="/private",
    tags=["private"],
    dependencies=[RequireSetup],
)


def _friend_list_available(status: str) -> bool:
    return status == "ok"


def _normalized_user_ids(user_ids: list[str]) -> list[str]:
    return sorted({str(uid).strip() for uid in user_ids if str(uid).strip()})


async def _ensure_friend_list_complete_for_mutation() -> None:
    invalidate_user_list_cache()
    _, fetch_status = await get_friend_list_with_availability()
    if fetch_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="好友列表不完整，暂不可修改策略",
        )


@router.get("/friends", response_model=FriendListResponse)
async def list_friends(_: AdminUser):
    users = await get_friend_list()
    return FriendListResponse(friends=[FriendInfo(**user) for user in users])


@router.get("/message-policy", response_model=PrivateMessagePolicyResponse)
async def get_message_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    invalidate_user_list_cache()
    users, fetch_status = await get_friend_list_with_availability()
    available = _friend_list_available(fetch_status)
    return PrivateMessagePolicyResponse(
        restrict=snap.message_private_restrict,
        enabled_user_ids=snap.message_enabled_user_ids,
        users=[]
        if fetch_status == "offline"
        else [FriendInfo(**user) for user in users],
        friend_list_available=available,
    )


@router.put("/message-policy", response_model=PrivateMessagePolicyResponse)
async def update_message_policy(
    body: PrivateMessagePolicyUpdateRequest,
    _: AdminUser,
):
    await _ensure_friend_list_complete_for_mutation()
    svc = get_config_service()
    enabled_ids = [
        str(uid).strip() for uid in body.enabled_user_ids if str(uid).strip()
    ]
    await svc.set_settings(
        {
            "message_private_restrict": str(body.restrict).lower(),
            "message_enabled_user_ids": json.dumps(enabled_ids, ensure_ascii=False),
        }
    )
    await svc.reload()
    invalidate_user_list_cache()

    snap = svc.get_snapshot()
    users, fetch_status = await get_friend_list_with_availability()
    return PrivateMessagePolicyResponse(
        restrict=snap.message_private_restrict,
        enabled_user_ids=snap.message_enabled_user_ids,
        users=[]
        if fetch_status == "offline"
        else [FriendInfo(**user) for user in users],
        friend_list_available=_friend_list_available(fetch_status),
    )


def _status_display_options(snap) -> StatusCheckDisplayOptions:
    return StatusCheckDisplayOptions(
        show_detailed=snap.status_check_show_detailed,
        show_uptime=snap.status_check_show_uptime,
        show_memory=snap.status_check_show_memory,
    )


def _message_enabled_users(snap, users: list[dict]) -> list[dict]:
    return [
        user
        for user in users
        if is_private_message_enabled_from_snapshot(str(user["user_id"]), snap)
    ]


def _ensure_private_message_enabled(user_id: str, snap) -> None:
    if not is_private_message_enabled_from_snapshot(user_id, snap):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户未启用好友消息，无法配置状态查询",
        )


def _status_policy_response(
    snap, users: list[dict], *, friend_list_available: bool
) -> PrivateStatusPolicyResponse:
    return PrivateStatusPolicyResponse(
        restrict=snap.status_check_private_restrict,
        enabled_user_ids=filter_enabled_user_ids_to_visible_users(
            snap.status_check_enabled_user_ids,
            users,
            friend_list_available=friend_list_available,
        ),
        users=[FriendInfo(**user) for user in users],
        display=_status_display_options(snap),
        friend_list_available=friend_list_available,
    )


@router.get("/status-policy", response_model=PrivateStatusPolicyResponse)
async def get_status_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    invalidate_user_list_cache()
    friends, fetch_status = await get_friend_list_with_availability()
    available = _friend_list_available(fetch_status)
    users = [] if fetch_status == "offline" else _message_enabled_users(snap, friends)
    return _status_policy_response(snap, users, friend_list_available=available)


@router.put("/status-policy", response_model=PrivateStatusPolicyResponse)
async def update_status_policy(
    body: PrivateStatusPolicyUpdateRequest,
    _: AdminUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    invalidate_user_list_cache()
    friends, fetch_status = await get_friend_list_with_availability()
    available = _friend_list_available(fetch_status)
    message_users = (
        [] if fetch_status == "offline" else _message_enabled_users(snap, friends)
    )
    body_enabled_ids = [
        str(uid).strip() for uid in body.enabled_user_ids if str(uid).strip()
    ]

    if not available:
        whitelist_changed = body.restrict != snap.status_check_private_restrict or (
            _normalized_user_ids(body_enabled_ids)
            != _normalized_user_ids(snap.status_check_enabled_user_ids)
        )
        if whitelist_changed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="好友列表不完整，暂不可修改状态查询白名单",
            )
        enabled_ids = list(snap.status_check_enabled_user_ids)
        restrict = snap.status_check_private_restrict
    else:
        enabled_ids = body_enabled_ids
        restrict = body.restrict
        for user_id in enabled_ids:
            _ensure_private_message_enabled(user_id, snap)
        enabled_ids = filter_enabled_user_ids_to_visible_users(
            enabled_ids,
            message_users,
            friend_list_available=True,
        )

    updates: dict[str, str] = {
        "status_check_private_restrict": str(restrict).lower(),
        "status_check_enabled_user_ids": json.dumps(enabled_ids, ensure_ascii=False),
    }
    if body.display is not None:
        updates["status_check_show_detailed"] = str(body.display.show_detailed).lower()
        updates["status_check_show_uptime"] = str(body.display.show_uptime).lower()
        updates["status_check_show_memory"] = str(body.display.show_memory).lower()

    await svc.set_settings(updates)
    await svc.reload()
    invalidate_user_list_cache()

    snap = svc.get_snapshot()
    friends, fetch_status = await get_friend_list_with_availability()
    available = _friend_list_available(fetch_status)
    users = [] if fetch_status == "offline" else _message_enabled_users(snap, friends)
    return _status_policy_response(snap, users, friend_list_available=available)
