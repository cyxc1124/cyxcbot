"""Link parser per-group / per-user policy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.link_parser import (
    LinkParserGlobalPolicy,
    LinkParserGroupPolicyItem,
    LinkParserGroupPolicyListResponse,
    LinkParserGroupPolicyMutationResponse,
    LinkParserGroupPolicyUpdateRequest,
    LinkParserUserPolicyCreateRequest,
    LinkParserUserPolicyItem,
    LinkParserUserPolicyListResponse,
    LinkParserUserPolicyMutationResponse,
    LinkParserUserPolicyUpdateRequest,
)
from admin.services.onebot_bridge import get_friend_list, get_group_list, invalidate_user_list_cache
from shared.audit.service import write_audit, write_system_event
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


def _group_policy_values(snap, group_id: str) -> tuple[bool, bool, bool, bool]:
    override = snap.link_parser_group_policies.get(group_id)
    if override:
        return override.enabled, override.video_enabled, override.live_enabled, True
    return (
        snap.bilibili_link_parser_enabled,
        snap.bilibili_link_parser_video_enabled,
        snap.bilibili_link_parser_live_enabled,
        False,
    )


def _user_policy_values(snap, user_id: str) -> tuple[bool, bool, bool, bool, bool]:
    override = snap.link_parser_user_policies.get(user_id)
    if override:
        return (
            override.enabled,
            override.video_enabled,
            override.live_enabled,
            override.private_enabled,
            True,
        )
    return (
        snap.bilibili_link_parser_enabled,
        snap.bilibili_link_parser_video_enabled,
        snap.bilibili_link_parser_live_enabled,
        snap.bilibili_link_parser_private_enabled,
        False,
    )


def _build_group_item(snap, group: dict) -> LinkParserGroupPolicyItem:
    group_id = str(group["group_id"])
    enabled, video_enabled, live_enabled, customized = _group_policy_values(snap, group_id)
    override = snap.link_parser_group_policies.get(group_id)
    return LinkParserGroupPolicyItem(
        group_id=group_id,
        group_name=group.get("group_name"),
        member_count=group.get("member_count"),
        customized=customized,
        enabled=enabled,
        video_enabled=video_enabled,
        live_enabled=live_enabled,
    )


def _build_group_items(snap, groups: list[dict]) -> list[LinkParserGroupPolicyItem]:
    return [_build_group_item(snap, group) for group in groups]


def _build_user_item(snap, user: dict) -> LinkParserUserPolicyItem:
    user_id = str(user["user_id"])
    enabled, video_enabled, live_enabled, private_enabled, customized = _user_policy_values(
        snap, user_id
    )
    override = snap.link_parser_user_policies.get(user_id)
    return LinkParserUserPolicyItem(
        user_id=user_id,
        nickname=user.get("nickname"),
        name=override.name if override else None,
        customized=customized,
        enabled=enabled,
        video_enabled=video_enabled,
        live_enabled=live_enabled,
        private_enabled=private_enabled,
    )


def _build_user_items(snap, users: list[dict]) -> list[LinkParserUserPolicyItem]:
    by_id: dict[str, dict] = {str(user["user_id"]): user for user in users}

    for user_id, record in snap.link_parser_user_policies.items():
        if user_id not in by_id:
            by_id[user_id] = {"user_id": user_id, "nickname": record.name}

    return [_build_user_item(snap, by_id[user_id]) for user_id in sorted(by_id.keys(), key=lambda value: (not value.isdigit(), value))]


def _group_matches_global(snap, body: LinkParserGroupPolicyUpdateRequest) -> bool:
    return (
        body.enabled == snap.bilibili_link_parser_enabled
        and body.video_enabled == snap.bilibili_link_parser_video_enabled
        and body.live_enabled == snap.bilibili_link_parser_live_enabled
    )


def _user_matches_global(snap, body: LinkParserUserPolicyUpdateRequest) -> bool:
    return (
        body.enabled == snap.bilibili_link_parser_enabled
        and body.video_enabled == snap.bilibili_link_parser_video_enabled
        and body.live_enabled == snap.bilibili_link_parser_live_enabled
        and body.private_enabled == snap.bilibili_link_parser_private_enabled
    )


async def _group_meta(group_id: str) -> dict:
    groups = await get_group_list()
    for group in groups:
        if str(group["group_id"]) == str(group_id):
            return group
    return {"group_id": str(group_id)}


async def _user_meta(user_id: str, snap) -> dict:
    users = await get_friend_list()
    for user in users:
        if str(user["user_id"]) == str(user_id):
            return user
    return {"user_id": str(user_id)}


async def _list_user_policy_response(snap, *, refresh_users: bool = False) -> LinkParserUserPolicyListResponse:
    if refresh_users:
        invalidate_user_list_cache()
    users = await get_friend_list()
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


@router.put("/groups/{group_id}", response_model=LinkParserGroupPolicyMutationResponse)
async def update_group_policy(
    group_id: str,
    body: LinkParserGroupPolicyUpdateRequest,
    request: Request,
    user: CurrentUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)

    if _group_matches_global(snap, body):
        await svc.delete_link_parser_group_policy(group_id)
    else:
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
    group = await _group_meta(group_id)
    return LinkParserGroupPolicyMutationResponse(
        global_policy=_global_policy(snap),
        item=_build_group_item(snap, group),
    )


@router.delete("/groups/{group_id}", response_model=LinkParserGroupPolicyMutationResponse)
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
    group = await _group_meta(group_id)
    return LinkParserGroupPolicyMutationResponse(
        global_policy=_global_policy(snap),
        item=_build_group_item(snap, group),
    )


@router.get("/users", response_model=LinkParserUserPolicyListResponse)
async def list_user_policies(_: CurrentUser):
    svc = get_config_service()
    return await _list_user_policy_response(svc.get_snapshot(), refresh_users=True)


@router.post("/users", response_model=LinkParserUserPolicyMutationResponse, status_code=status.HTTP_201_CREATED)
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

    snap = svc.get_snapshot()
    user_meta = await _user_meta(user_id, snap)
    return LinkParserUserPolicyMutationResponse(
        global_policy=_global_policy(snap),
        item=_build_user_item(snap, user_meta),
    )


@router.put("/users/{user_id}", response_model=LinkParserUserPolicyMutationResponse)
async def update_user_policy(
    user_id: str,
    body: LinkParserUserPolicyUpdateRequest,
    request: Request,
    user: CurrentUser,
):
    svc = get_config_service()
    snap = svc.get_snapshot()
    existing = snap.link_parser_user_policies.get(user_id)

    if _user_matches_global(snap, body):
        await svc.delete_link_parser_user_policy(user_id)
    else:
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

    snap = svc.get_snapshot()
    user_meta = await _user_meta(user_id, snap)
    return LinkParserUserPolicyMutationResponse(
        global_policy=_global_policy(snap),
        item=_build_user_item(snap, user_meta),
    )


@router.delete("/users/{user_id}", response_model=LinkParserUserPolicyMutationResponse)
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

    snap = svc.get_snapshot()
    user_meta = await _user_meta(user_id, snap)
    return LinkParserUserPolicyMutationResponse(
        global_policy=_global_policy(snap),
        item=_build_user_item(snap, user_meta),
    )
