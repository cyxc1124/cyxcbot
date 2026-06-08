"""OneBot group list and message policy endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.groups import (
    GroupInfo,
    GroupListResponse,
    GroupMessagePolicyResponse,
    GroupMessagePolicyUpdateRequest,
)
from admin.services.onebot_bridge import get_group_list
from shared.audit.service import write_audit, write_system_event
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    dependencies=[RequireSetup],
)


@router.get("", response_model=GroupListResponse)
async def list_groups(_: CurrentUser):
    groups = await get_group_list()
    return GroupListResponse(groups=[GroupInfo(**g) for g in groups])


@router.get("/message-policy", response_model=GroupMessagePolicyResponse)
async def get_message_policy(_: CurrentUser):
    snap = get_config_service().get_snapshot()
    groups = await get_group_list()
    return GroupMessagePolicyResponse(
        restrict=snap.message_group_restrict,
        enabled_group_ids=snap.message_enabled_group_ids,
        groups=[GroupInfo(**g) for g in groups],
    )


@router.put("/message-policy", response_model=GroupMessagePolicyResponse)
async def update_message_policy(
    request: Request,
    body: GroupMessagePolicyUpdateRequest,
    user: CurrentUser,
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

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details(
            {
                "message_group_restrict": body.restrict,
                "message_enabled_group_ids": enabled_ids,
                "source": "group_message_policy",
            }
        ),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Group message policy updated")

    snap = svc.get_snapshot()
    groups = await get_group_list()
    return GroupMessagePolicyResponse(
        restrict=snap.message_group_restrict,
        enabled_group_ids=snap.message_enabled_group_ids,
        groups=[GroupInfo(**g) for g in groups],
    )
