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
from admin.services.onebot_bridge import get_friend_list, invalidate_user_list_cache
from shared.config.service import get_config_service
from shared.private_policy import is_private_message_enabled_from_snapshot

router = APIRouter(
    prefix="/private",
    tags=["private"],
    dependencies=[RequireSetup],
)


@router.get("/friends", response_model=FriendListResponse)
async def list_friends(_: AdminUser):
    users = await get_friend_list()
    return FriendListResponse(friends=[FriendInfo(**user) for user in users])


@router.get("/message-policy", response_model=PrivateMessagePolicyResponse)
async def get_message_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    users = await get_friend_list()
    return PrivateMessagePolicyResponse(
        restrict=snap.message_private_restrict,
        enabled_user_ids=snap.message_enabled_user_ids,
        users=[FriendInfo(**user) for user in users],
    )


@router.put("/message-policy", response_model=PrivateMessagePolicyResponse)
async def update_message_policy(
    body: PrivateMessagePolicyUpdateRequest,
    _: AdminUser,
):
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
    users = await get_friend_list()
    return PrivateMessagePolicyResponse(
        restrict=snap.message_private_restrict,
        enabled_user_ids=snap.message_enabled_user_ids,
        users=[FriendInfo(**user) for user in users],
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


def _filter_status_enabled_user_ids(
    enabled_ids: list[str], users: list[dict]
) -> list[str]:
    allowed = {str(user["user_id"]) for user in users}
    return [uid for uid in enabled_ids if uid in allowed]


@router.get("/status-policy", response_model=PrivateStatusPolicyResponse)
async def get_status_policy(_: AdminUser):
    snap = get_config_service().get_snapshot()
    users = _message_enabled_users(snap, await get_friend_list())
    return PrivateStatusPolicyResponse(
        restrict=snap.status_check_private_restrict,
        enabled_user_ids=_filter_status_enabled_user_ids(
            snap.status_check_enabled_user_ids, users
        ),
        users=[FriendInfo(**user) for user in users],
        display=_status_display_options(snap),
    )


@router.put("/status-policy", response_model=PrivateStatusPolicyResponse)
async def update_status_policy(
    body: PrivateStatusPolicyUpdateRequest,
    _: AdminUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    message_users = _message_enabled_users(snap, await get_friend_list())
    enabled_ids = [
        str(uid).strip() for uid in body.enabled_user_ids if str(uid).strip()
    ]
    for user_id in enabled_ids:
        _ensure_private_message_enabled(user_id, snap)
    enabled_ids = _filter_status_enabled_user_ids(enabled_ids, message_users)
    updates: dict[str, str] = {
        "status_check_private_restrict": str(body.restrict).lower(),
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
    users = _message_enabled_users(snap, await get_friend_list())
    return PrivateStatusPolicyResponse(
        restrict=snap.status_check_private_restrict,
        enabled_user_ids=_filter_status_enabled_user_ids(
            snap.status_check_enabled_user_ids, users
        ),
        users=[FriendInfo(**user) for user in users],
        display=_status_display_options(snap),
    )
