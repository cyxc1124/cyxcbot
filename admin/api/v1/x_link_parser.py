"""X link parser policy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.x_link_parser import (
    XLinkParserGroupPolicyItem,
    XLinkParserGroupPolicyListResponse,
    XLinkParserGroupPolicyMutationResponse,
    XLinkParserGroupPolicyUpdateRequest,
    XLinkParserUserPolicyCreateRequest,
    XLinkParserUserPolicyItem,
    XLinkParserUserPolicyListResponse,
    XLinkParserUserPolicyMutationResponse,
    XLinkParserUserPolicyUpdateRequest,
)
from admin.services.link_parser_policy_items import onebot_list_listing_mode
from admin.services.onebot_bridge import (
    get_friend_list,
    get_friend_list_with_availability,
    get_group_list,
    get_group_list_with_status,
    invalidate_user_list_cache,
)
from shared.config.service import get_config_service
from shared.group_policy import is_group_message_enabled_from_snapshot
from shared.private_policy import is_private_message_enabled_from_snapshot

router = APIRouter(
    prefix="/x-link-parser",
    tags=["x-link-parser"],
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
            detail="该用户未启用好友消息，无法配置 X 链接解析",
        )


def _ensure_group_message_enabled(group_id: str, snap) -> None:
    if not is_group_message_enabled_from_snapshot(group_id, snap):
        raise HTTPException(
            status_code=400,
            detail="该群未启用群消息，无法配置 X 链接解析",
        )


def _group_policy_values(snap, group_id: str) -> tuple[bool, bool]:
    override = snap.x_link_parser_group_policies.get(str(group_id).strip())
    if override:
        return override.enabled, True
    return False, False


def _user_policy_values(snap, user_id: str) -> tuple[bool, bool]:
    override = snap.x_link_parser_user_policies.get(str(user_id).strip())
    if override:
        return override.enabled, True
    return False, False


def _build_group_item(snap, group: dict) -> XLinkParserGroupPolicyItem:
    group_id = str(group["group_id"])
    enabled, customized = _group_policy_values(snap, group_id)
    return XLinkParserGroupPolicyItem(
        group_id=group_id,
        group_name=group.get("group_name"),
        member_count=group.get("member_count"),
        customized=customized,
        enabled=enabled,
    )


def _build_user_item(snap, user: dict) -> XLinkParserUserPolicyItem:
    user_id = str(user["user_id"])
    enabled, customized = _user_policy_values(snap, user_id)
    override = snap.x_link_parser_user_policies.get(user_id)
    return XLinkParserUserPolicyItem(
        user_id=user_id,
        nickname=user.get("nickname"),
        name=override.name if override else None,
        customized=customized,
        enabled=enabled,
    )


def _build_user_items(
    snap,
    users: list[dict],
    *,
    include_configured_non_friends: bool = False,
) -> list[XLinkParserUserPolicyItem]:
    by_id: dict[str, dict] = {str(user["user_id"]): user for user in users}
    if include_configured_non_friends:
        for user_id, record in snap.x_link_parser_user_policies.items():
            if user_id in by_id:
                continue
            if not is_private_message_enabled_from_snapshot(user_id, snap):
                continue
            by_id[user_id] = {"user_id": user_id, "nickname": record.name}
    return [
        _build_user_item(snap, by_id[user_id])
        for user_id in sorted(
            by_id.keys(), key=lambda value: (not value.isdigit(), value)
        )
    ]


async def _ensure_friend_list_complete_for_mutation() -> None:
    invalidate_user_list_cache()
    _, fetch_status = await get_friend_list_with_availability()
    if fetch_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="好友列表不完整，暂不可修改 X 链接解析策略",
        )


async def _ensure_group_list_complete_for_mutation() -> None:
    _, fetch_status = await get_group_list_with_status()
    if fetch_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="群列表不完整，暂不可修改 X 链接解析策略",
        )


async def _group_meta(group_id: str) -> dict:
    groups = await get_group_list()
    for group in groups:
        if str(group["group_id"]) == str(group_id):
            return group
    return {"group_id": str(group_id)}


async def _user_meta(user_id: str) -> dict:
    users = await get_friend_list()
    for user in users:
        if str(user["user_id"]) == str(user_id):
            return user
    return {"user_id": str(user_id)}


@router.get("/policies/groups", response_model=XLinkParserGroupPolicyListResponse)
async def list_group_policies(_: AdminUser):
    svc = get_config_service()
    snap = svc.get_snapshot()
    groups, fetch_status = await get_group_list_with_status()
    mode = onebot_list_listing_mode(fetch_status)
    if mode == "empty":
        return XLinkParserGroupPolicyListResponse(groups=[], group_list_available=False)
    visible = _message_enabled_groups(snap, groups)
    return XLinkParserGroupPolicyListResponse(
        groups=[_build_group_item(snap, group) for group in visible],
        group_list_available=(mode == "map"),
    )


@router.put(
    "/policies/groups/{group_id}",
    response_model=XLinkParserGroupPolicyMutationResponse,
)
async def update_group_policy(
    group_id: str,
    body: XLinkParserGroupPolicyUpdateRequest,
    _: AdminUser,
):
    await _ensure_group_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)

    if not body.enabled:
        await svc.delete_x_link_parser_group_policy(group_id)
    else:
        await svc.upsert_x_link_parser_group_policy(group_id, enabled=True)
    await svc.reload()

    snap = svc.get_snapshot()
    group = await _group_meta(group_id)
    return XLinkParserGroupPolicyMutationResponse(
        item=_build_group_item(snap, group),
    )


@router.delete(
    "/policies/groups/{group_id}",
    response_model=XLinkParserGroupPolicyMutationResponse,
)
async def reset_group_policy(group_id: str, _: AdminUser):
    await _ensure_group_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)
    await svc.delete_x_link_parser_group_policy(group_id)
    await svc.reload()
    snap = svc.get_snapshot()
    group = await _group_meta(group_id)
    return XLinkParserGroupPolicyMutationResponse(
        item=_build_group_item(snap, group),
    )


@router.get("/policies/users", response_model=XLinkParserUserPolicyListResponse)
async def list_user_policies(_: AdminUser):
    svc = get_config_service()
    snap = svc.get_snapshot()
    invalidate_user_list_cache()
    friends, fetch_status = await get_friend_list_with_availability()
    mode = onebot_list_listing_mode(fetch_status)
    if mode == "empty":
        return XLinkParserUserPolicyListResponse(users=[], friend_list_available=False)
    users = _message_enabled_users(snap, friends)
    return XLinkParserUserPolicyListResponse(
        users=_build_user_items(
            snap, users, include_configured_non_friends=(mode == "map")
        ),
        friend_list_available=(mode == "map"),
    )


@router.post(
    "/policies/users",
    response_model=XLinkParserUserPolicyMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_policy(
    body: XLinkParserUserPolicyCreateRequest,
    _: AdminUser,
):
    user_id = body.user_id.strip()
    if not user_id.isdigit():
        raise HTTPException(status_code=400, detail="QQ 号必须为数字")

    await _ensure_friend_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_private_message_enabled(user_id, snap)
    if user_id in snap.x_link_parser_user_policies:
        raise HTTPException(status_code=409, detail="该用户策略已存在")

    if body.enabled:
        await svc.upsert_x_link_parser_user_policy(
            user_id, enabled=True, name=body.name
        )
    await svc.reload()
    snap = svc.get_snapshot()
    return XLinkParserUserPolicyMutationResponse(
        item=_build_user_item(snap, await _user_meta(user_id)),
    )


@router.put(
    "/policies/users/{user_id}",
    response_model=XLinkParserUserPolicyMutationResponse,
)
async def update_user_policy(
    user_id: str,
    body: XLinkParserUserPolicyUpdateRequest,
    _: AdminUser,
):
    await _ensure_friend_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_private_message_enabled(user_id, snap)
    existing = snap.x_link_parser_user_policies.get(user_id)

    if not body.enabled:
        await svc.delete_x_link_parser_user_policy(user_id)
    else:
        await svc.upsert_x_link_parser_user_policy(
            user_id,
            enabled=True,
            name=body.name
            if body.name is not None
            else (existing.name if existing else None),
        )
    await svc.reload()
    snap = svc.get_snapshot()
    return XLinkParserUserPolicyMutationResponse(
        item=_build_user_item(snap, await _user_meta(user_id)),
    )


@router.delete(
    "/policies/users/{user_id}",
    response_model=XLinkParserUserPolicyMutationResponse,
)
async def reset_user_policy(user_id: str, _: AdminUser):
    await _ensure_friend_list_complete_for_mutation()
    svc = get_config_service()
    await svc.delete_x_link_parser_user_policy(user_id)
    await svc.reload()
    snap = svc.get_snapshot()
    return XLinkParserUserPolicyMutationResponse(
        item=_build_user_item(snap, await _user_meta(user_id)),
    )
