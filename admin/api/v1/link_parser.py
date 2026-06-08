"""Link parser per-group / per-user policy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.link_parser import (
    LinkParserGlobalPolicy,
    LinkParserGroupPolicyItem,
    LinkParserGroupPolicyListResponse,
    LinkParserGroupPolicyUpdateRequest,
    LinkParserUserPolicyCreateRequest,
    LinkParserUserPolicyItem,
    LinkParserUserPolicyListResponse,
    LinkParserUserPolicyUpdateRequest,
)
from admin.services.onebot_bridge import get_group_list, get_user_list
from shared.audit.service import write_audit, write_system_event
from shared.config.link_parser_policy import resolve_link_parser_policy
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType
from shared.group_policy import is_group_message_enabled_from_snapshot

router = APIRouter(
    prefix="/link-parser/policies",
    tags=["link-parser"],
    dependencies=[RequireSetup],
)


def _global_policy(snap) -> LinkParserGlobalPolicy:
    return LinkParserGlobalPolicy(
        enabled=snap.bilibili_link_parser_enabled,
        video_enabled=snap.bilibili_link_parser_video_enabled,
        live_enabled=snap.bilibili_link_parser_live_enabled,
        private_enabled=snap.bilibili_link_parser_private_enabled,
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
            status_code=400,
            detail="该群未启用群消息，无法配置链接解析",
        )


def _build_group_items(snap, groups: list[dict]) -> list[LinkParserGroupPolicyItem]:
    items: list[LinkParserGroupPolicyItem] = []
    for group in groups:
        group_id = str(group["group_id"])
        override = snap.link_parser_group_policies.get(group_id)
        effective = resolve_link_parser_policy(
            snap,
            group_id=group_id,
            user_id=None,
            is_private=False,
        )
        items.append(
            LinkParserGroupPolicyItem(
                group_id=group_id,
                group_name=group.get("group_name"),
                member_count=group.get("member_count"),
                customized=override is not None,
                enabled=effective.enabled,
                video_enabled=effective.video_enabled,
                live_enabled=effective.live_enabled,
            )
        )
    return items


def _build_user_items(snap, users: list[dict]) -> list[LinkParserUserPolicyItem]:
    by_id: dict[str, dict] = {str(user["user_id"]): user for user in users}

    for user_id, record in snap.link_parser_user_policies.items():
        if user_id not in by_id:
            by_id[user_id] = {"user_id": user_id, "nickname": record.name}

    items: list[LinkParserUserPolicyItem] = []
    for user_id in sorted(by_id.keys(), key=lambda value: (not value.isdigit(), value)):
        user = by_id[user_id]
        override = snap.link_parser_user_policies.get(user_id)
        effective = resolve_link_parser_policy(
            snap,
            user_id=user_id,
            is_private=True,
        )
        items.append(
            LinkParserUserPolicyItem(
                user_id=user_id,
                nickname=user.get("nickname"),
                name=override.name if override else None,
                customized=override is not None,
                enabled=effective.enabled,
                video_enabled=effective.video_enabled,
                live_enabled=effective.live_enabled,
                private_enabled=effective.private_enabled,
            )
        )
    return items


async def _list_user_policy_response(snap) -> LinkParserUserPolicyListResponse:
    groups = _message_enabled_groups(snap, await get_group_list())
    group_ids = [str(group["group_id"]) for group in groups]
    users = await get_user_list(group_ids=group_ids)
    return LinkParserUserPolicyListResponse(
        global_policy=_global_policy(snap),
        users=_build_user_items(snap, users),
    )


@router.get("/groups", response_model=LinkParserGroupPolicyListResponse)
async def list_group_policies(_: CurrentUser):
    svc = get_config_service()
    snap = svc.get_snapshot()
    groups = _message_enabled_groups(snap, await get_group_list())
    return LinkParserGroupPolicyListResponse(
        global_policy=_global_policy(snap),
        groups=_build_group_items(snap, groups),
    )


@router.put("/groups/{group_id}", response_model=LinkParserGroupPolicyListResponse)
async def update_group_policy(
    group_id: str,
    body: LinkParserGroupPolicyUpdateRequest,
    request: Request,
    user: CurrentUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)
    await svc.upsert_link_parser_group_policy(
        group_id,
        enabled=body.enabled,
        video_enabled=body.video_enabled,
        live_enabled=body.live_enabled,
    )
    await svc.reload()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details({"link_parser_group_policy": group_id, **body.model_dump()}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Link parser group policy updated")

    snap = svc.get_snapshot()
    groups = _message_enabled_groups(snap, await get_group_list())
    return LinkParserGroupPolicyListResponse(
        global_policy=_global_policy(snap),
        groups=_build_group_items(snap, groups),
    )


@router.delete("/groups/{group_id}", response_model=LinkParserGroupPolicyListResponse)
async def reset_group_policy(group_id: str, request: Request, user: CurrentUser):
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)
    await svc.delete_link_parser_group_policy(group_id)
    await svc.reload()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details(
            {"link_parser_group_policy_reset": group_id, "source": "link_parser_policy"}
        ),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Link parser group policy reset")

    snap = svc.get_snapshot()
    groups = _message_enabled_groups(snap, await get_group_list())
    return LinkParserGroupPolicyListResponse(
        global_policy=_global_policy(snap),
        groups=_build_group_items(snap, groups),
    )


@router.get("/users", response_model=LinkParserUserPolicyListResponse)
async def list_user_policies(_: CurrentUser):
    svc = get_config_service()
    return await _list_user_policy_response(svc.get_snapshot())


@router.post("/users", response_model=LinkParserUserPolicyListResponse, status_code=status.HTTP_201_CREATED)
async def create_user_policy(
    body: LinkParserUserPolicyCreateRequest,
    request: Request,
    user: CurrentUser,
):
    user_id = body.user_id.strip()
    if not user_id.isdigit():
        raise HTTPException(status_code=400, detail="QQ 号必须为数字")

    svc = get_config_service()
    if user_id in svc.get_snapshot().link_parser_user_policies:
        raise HTTPException(status_code=409, detail="该用户策略已存在")

    await svc.upsert_link_parser_user_policy(
        user_id,
        enabled=body.enabled,
        video_enabled=body.video_enabled,
        live_enabled=body.live_enabled,
        private_enabled=body.private_enabled,
        name=body.name,
    )
    await svc.reload()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details({"link_parser_user_policy_create": user_id}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Link parser user policy created")

    return await _list_user_policy_response(svc.get_snapshot())


@router.put("/users/{user_id}", response_model=LinkParserUserPolicyListResponse)
async def update_user_policy(
    user_id: str,
    body: LinkParserUserPolicyUpdateRequest,
    request: Request,
    user: CurrentUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    existing = snap.link_parser_user_policies.get(user_id)
    await svc.upsert_link_parser_user_policy(
        user_id,
        enabled=body.enabled,
        video_enabled=body.video_enabled,
        live_enabled=body.live_enabled,
        private_enabled=body.private_enabled,
        name=body.name if body.name is not None else (existing.name if existing else None),
    )
    await svc.reload()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details({"link_parser_user_policy": user_id, **body.model_dump()}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Link parser user policy updated")

    return await _list_user_policy_response(svc.get_snapshot())


@router.delete("/users/{user_id}", response_model=LinkParserUserPolicyListResponse)
async def reset_user_policy(user_id: str, request: Request, user: CurrentUser):
    svc = get_config_service()
    await svc.delete_link_parser_user_policy(user_id)
    await svc.reload()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.SETTINGS_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=svc.serialize_details(
            {"link_parser_user_policy_reset": user_id, "source": "link_parser_policy"}
        ),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, "Link parser user policy reset")

    return await _list_user_policy_response(svc.get_snapshot())
