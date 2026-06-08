"""OneBot friend list and private message policy endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.private import (
    FriendInfo,
    FriendListResponse,
    PrivateMessagePolicyResponse,
    PrivateMessagePolicyUpdateRequest,
)
from admin.services.onebot_bridge import get_friend_list, invalidate_user_list_cache
from shared.audit.service import write_audit, write_system_event
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType

router = APIRouter(
    prefix="/private",
    tags=["private"],
    dependencies=[RequireSetup],
)


@router.get("/friends", response_model=FriendListResponse)
async def list_friends(_: CurrentUser):
    users = await get_friend_list()
    return FriendListResponse(friends=[FriendInfo(**user) for user in users])


@router.get("/message-policy", response_model=PrivateMessagePolicyResponse)
async def get_message_policy(_: CurrentUser):
    snap = get_config_service().get_snapshot()
    users = await get_friend_list()
    return PrivateMessagePolicyResponse(
        restrict=snap.message_private_restrict,
        enabled_user_ids=snap.message_enabled_user_ids,
        users=[FriendInfo(**user) for user in users],
    )


@router.put("/message-policy", response_model=PrivateMessagePolicyResponse)
async def update_message_policy(
    request: Request,
    body: PrivateMessagePolicyUpdateRequest,
    user: CurrentUser,
):
    svc = get_config_service()
    enabled_ids = [str(uid).strip() for uid in body.enabled_user_ids if str(uid).strip()]
    await svc.set_settings(
        {
            "message_private_restrict": str(body.restrict).lower(),
            "message_enabled_user_ids": json.dumps(enabled_ids, ensure_ascii=False),
        }
    )
    await svc.reload()
    invalidate_user_list_cache()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details(
            {
                "message_private_restrict": body.restrict,
                "message_enabled_user_ids": enabled_ids,
                "source": "private_message_policy",
            }
        ),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Private message policy updated")

    snap = svc.get_snapshot()
    users = await get_friend_list()
    return PrivateMessagePolicyResponse(
        restrict=snap.message_private_restrict,
        enabled_user_ids=snap.message_enabled_user_ids,
        users=[FriendInfo(**user) for user in users],
    )
