"""Link parser per-group / per-user policy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.link_parser import (
    LinkParserGroupPolicyItem,
    LinkParserGroupPolicyListResponse,
    LinkParserGroupPolicyMutationResponse,
    LinkParserGroupPolicyUpdateRequest,
    LinkParserUserPolicyCreateRequest,
    LinkParserUserPolicyListResponse,
    LinkParserUserPolicyMutationResponse,
    LinkParserUserPolicyUpdateRequest,
)
from admin.services.link_parser_access import (
    ensure_link_parser_target_editable,
    link_parser_policy_rows,
)
from admin.services.link_parser_policy_items import (
    build_user_policy_item,
    build_user_policy_items,
    onebot_list_listing_mode,
)
from admin.services.onebot_bridge import (
    get_friend_list_with_availability,
    get_group_list_with_status,
    invalidate_user_list_cache,
)
from shared.config.link_parser_policy import normalize_link_parser_flags
from shared.config.service import get_config_service
from shared.group_policy import is_group_message_enabled_from_snapshot
from shared.private_policy import is_private_message_enabled_from_snapshot

router = APIRouter(
    prefix="/link-parser/policies",
    tags=["link-parser"],
    dependencies=[RequireSetup],
)


def _message_enabled_groups(snap, groups: list[dict]) -> list[dict]:
    return [
        group
        for group in groups
        if is_group_message_enabled_from_snapshot(str(group["group_id"]), snap)
    ]


def _message_enabled_users(snap, users: list[dict]) -> list[dict]:
    return [
        user
        for user in users
        if is_private_message_enabled_from_snapshot(str(user["user_id"]), snap)
    ]


def _ensure_private_message_enabled(user_id: str, snap) -> None:
    if not is_private_message_enabled_from_snapshot(user_id, snap):
        raise HTTPException(
            status_code=400,
            detail="该用户未启用好友消息，无法配置链接解析",
        )


def _ensure_group_message_enabled(group_id: str, snap) -> None:
    if not is_group_message_enabled_from_snapshot(group_id, snap):
        raise HTTPException(
            status_code=400,
            detail="该群未启用群消息，无法配置链接解析",
        )


def _group_policy_values(snap, group_id: str) -> tuple[bool, bool, bool, bool, bool]:
    override = snap.link_parser_group_policies.get(str(group_id).strip())
    if override:
        video, live, dynamic, send = normalize_link_parser_flags(
            video_enabled=override.video_enabled,
            live_enabled=override.live_enabled,
            dynamic_enabled=override.dynamic_enabled,
            send_video_enabled=override.send_video_enabled,
        )
        return video, live, dynamic, send, True
    return False, False, False, False, False


def _build_group_item(snap, group: dict) -> LinkParserGroupPolicyItem:
    group_id = str(group["group_id"])
    (
        video_enabled,
        live_enabled,
        dynamic_enabled,
        send_video_enabled,
        customized,
    ) = _group_policy_values(snap, group_id)
    return LinkParserGroupPolicyItem(
        group_id=group_id,
        group_name=group.get("group_name"),
        member_count=group.get("member_count"),
        source=group.get("source", "onebot"),
        editable=group.get("editable", True),
        customized=customized,
        video_enabled=video_enabled,
        live_enabled=live_enabled,
        dynamic_enabled=dynamic_enabled,
        send_video_enabled=send_video_enabled,
    )


def _build_group_items(snap, groups: list[dict]) -> list[LinkParserGroupPolicyItem]:
    return [_build_group_item(snap, group) for group in groups]


def _normalized_body_flags(
    body: (
        LinkParserGroupPolicyUpdateRequest
        | LinkParserUserPolicyUpdateRequest
        | LinkParserUserPolicyCreateRequest
    ),
) -> tuple[bool, bool, bool, bool]:
    return normalize_link_parser_flags(
        video_enabled=body.video_enabled,
        live_enabled=body.live_enabled,
        dynamic_enabled=body.dynamic_enabled,
        send_video_enabled=body.send_video_enabled,
    )


def _is_default_off(
    body: (
        LinkParserGroupPolicyUpdateRequest
        | LinkParserUserPolicyUpdateRequest
        | LinkParserUserPolicyCreateRequest
    ),
) -> bool:
    video, live, dynamic, send = _normalized_body_flags(body)
    return not video and not live and not dynamic and not send


async def _ensure_user_editable(user_id: str) -> dict:
    # Always re-fetch: a TTL cache hit must not bypass the mutation guard after disconnect.
    invalidate_user_list_cache()
    users, fetch_status = await get_friend_list_with_availability()
    return ensure_link_parser_target_editable(
        user_id,
        users,
        fetch_status,
        id_key="user_id",
        detail="好友列表不完整或目标未知，暂不可修改链接解析策略",
    )


async def _ensure_group_editable(group_id: str) -> dict:
    groups, fetch_status = await get_group_list_with_status()
    return ensure_link_parser_target_editable(
        group_id,
        groups,
        fetch_status,
        id_key="group_id",
        detail="群列表不完整或目标未知，暂不可修改链接解析策略",
    )


async def _list_group_policy_response(snap) -> LinkParserGroupPolicyListResponse:
    groups, fetch_status = await get_group_list_with_status()
    visible = _message_enabled_groups(
        snap, link_parser_policy_rows(groups, fetch_status)
    )
    return LinkParserGroupPolicyListResponse(
        groups=_build_group_items(snap, visible),
        group_list_available=(fetch_status == "ok"),
        onebot_list_status=fetch_status,
    )


async def _list_user_policy_response(
    snap, *, refresh_users: bool = False
) -> LinkParserUserPolicyListResponse:
    if refresh_users:
        invalidate_user_list_cache()
    friends, fetch_status = await get_friend_list_with_availability()
    mode = onebot_list_listing_mode(fetch_status)
    users = _message_enabled_users(snap, link_parser_policy_rows(friends, fetch_status))
    return LinkParserUserPolicyListResponse(
        users=build_user_policy_items(
            snap,
            users,
            include_configured_non_friends=(mode == "map"),
        ),
        friend_list_available=(mode == "map"),
        onebot_list_status=fetch_status,
    )


@router.get("/groups", response_model=LinkParserGroupPolicyListResponse)
async def list_group_policies(_: AdminUser):
    svc = get_config_service()
    return await _list_group_policy_response(svc.get_snapshot())


@router.put("/groups/{group_id}", response_model=LinkParserGroupPolicyMutationResponse)
async def update_group_policy(
    group_id: str,
    body: LinkParserGroupPolicyUpdateRequest,
    _: AdminUser,
):
    group = await _ensure_group_editable(group_id)
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)

    video, live, dynamic, send = _normalized_body_flags(body)
    if _is_default_off(body):
        await svc.delete_link_parser_group_policy(group_id)
    else:
        await svc.upsert_link_parser_group_policy(
            group_id,
            video_enabled=video,
            live_enabled=live,
            dynamic_enabled=dynamic,
            send_video_enabled=send,
        )
    await svc.reload()

    snap = svc.get_snapshot()
    return LinkParserGroupPolicyMutationResponse(
        item=_build_group_item(snap, group),
    )


@router.delete(
    "/groups/{group_id}", response_model=LinkParserGroupPolicyMutationResponse
)
async def reset_group_policy(group_id: str, _: AdminUser):
    group = await _ensure_group_editable(group_id)
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)
    await svc.delete_link_parser_group_policy(group_id)
    await svc.reload()

    snap = svc.get_snapshot()
    return LinkParserGroupPolicyMutationResponse(
        item=_build_group_item(snap, group),
    )


@router.get("/users", response_model=LinkParserUserPolicyListResponse)
async def list_user_policies(_: AdminUser):
    svc = get_config_service()
    return await _list_user_policy_response(svc.get_snapshot(), refresh_users=True)


@router.post(
    "/users",
    response_model=LinkParserUserPolicyMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_policy(
    body: LinkParserUserPolicyCreateRequest,
    _: AdminUser,
):
    user_id = body.user_id.strip()
    user_meta = await _ensure_user_editable(user_id)
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_private_message_enabled(user_id, snap)
    if user_id in snap.link_parser_user_policies:
        raise HTTPException(status_code=409, detail="该用户策略已存在")

    video, live, dynamic, send = _normalized_body_flags(body)
    if not _is_default_off(body):
        await svc.upsert_link_parser_user_policy(
            user_id,
            video_enabled=video,
            live_enabled=live,
            dynamic_enabled=dynamic,
            send_video_enabled=send,
            name=body.name,
        )
    await svc.reload()

    snap = svc.get_snapshot()
    return LinkParserUserPolicyMutationResponse(
        item=build_user_policy_item(snap, user_meta),
    )


@router.put("/users/{user_id}", response_model=LinkParserUserPolicyMutationResponse)
async def update_user_policy(
    user_id: str,
    body: LinkParserUserPolicyUpdateRequest,
    _: AdminUser,
):
    user_meta = await _ensure_user_editable(user_id)
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_private_message_enabled(user_id, snap)
    existing = snap.link_parser_user_policies.get(user_id)

    video, live, dynamic, send = _normalized_body_flags(body)
    if _is_default_off(body):
        await svc.delete_link_parser_user_policy(user_id)
    else:
        await svc.upsert_link_parser_user_policy(
            user_id,
            video_enabled=video,
            live_enabled=live,
            dynamic_enabled=dynamic,
            send_video_enabled=send,
            name=body.name
            if body.name is not None
            else (existing.name if existing else None),
        )
    await svc.reload()

    snap = svc.get_snapshot()
    return LinkParserUserPolicyMutationResponse(
        item=build_user_policy_item(snap, user_meta),
    )


@router.delete("/users/{user_id}", response_model=LinkParserUserPolicyMutationResponse)
async def reset_user_policy(user_id: str, _: AdminUser):
    user_meta = await _ensure_user_editable(user_id)
    svc = get_config_service()
    _ensure_private_message_enabled(user_id, svc.get_snapshot())
    await svc.delete_link_parser_user_policy(user_id)
    await svc.reload()

    snap = svc.get_snapshot()
    return LinkParserUserPolicyMutationResponse(
        item=build_user_policy_item(snap, user_meta),
    )
