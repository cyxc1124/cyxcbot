"""Rust RCON per-group / per-user policy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.rust_rcon_policy import (
    RustRconGroupPolicyListResponse,
    RustRconGroupPolicyMutationResponse,
    RustRconGroupPolicyUpdateRequest,
    RustRconUserPolicyListResponse,
    RustRconUserPolicyMutationResponse,
    RustRconUserPolicyUpdateRequest,
)
from admin.services.onebot_bridge import (
    get_friend_list,
    get_friend_list_with_availability,
    get_group_list,
    get_group_list_with_status,
    invalidate_user_list_cache,
)
from admin.services.rust_rcon_policy_items import (
    build_group_policy_item,
    build_group_policy_items,
    build_user_policy_item,
    build_user_policy_items,
    onebot_list_listing_mode,
)
from shared.config.service import get_config_service
from shared.group_policy import is_group_message_enabled_from_snapshot
from shared.private_policy import is_private_message_enabled_from_snapshot

router = APIRouter(
    prefix="/rust-rcon/policies",
    tags=["rust-rcon"],
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
            detail="该用户未启用好友消息，无法配置 Rust RCON",
        )


def _ensure_group_message_enabled(group_id: str, snap) -> None:
    if not is_group_message_enabled_from_snapshot(group_id, snap):
        raise HTTPException(
            status_code=400,
            detail="该群未启用群消息，无法配置 Rust RCON",
        )


async def _group_meta(group_id: str) -> dict:
    groups = await get_group_list()
    for group in groups:
        if str(group["group_id"]) == str(group_id):
            return group
    return {"group_id": str(group_id)}


async def _ensure_friend_list_complete_for_mutation() -> None:
    invalidate_user_list_cache()
    _, fetch_status = await get_friend_list_with_availability()
    if fetch_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="好友列表不完整，暂不可修改 Rust RCON 策略",
        )


async def _ensure_group_list_complete_for_mutation() -> None:
    _, fetch_status = await get_group_list_with_status()
    if fetch_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="群列表不完整，暂不可修改 Rust RCON 策略",
        )


async def _list_group_policy_response(snap) -> RustRconGroupPolicyListResponse:
    groups, fetch_status = await get_group_list_with_status()
    mode = onebot_list_listing_mode(fetch_status)
    if mode == "empty":
        return RustRconGroupPolicyListResponse(
            groups=[],
            group_list_available=False,
        )
    visible = _message_enabled_groups(snap, groups)
    return RustRconGroupPolicyListResponse(
        groups=build_group_policy_items(snap, visible),
        group_list_available=(mode == "map"),
    )


async def _list_user_policy_response(
    snap, *, refresh_users: bool = False
) -> RustRconUserPolicyListResponse:
    if refresh_users:
        invalidate_user_list_cache()
    friends, fetch_status = await get_friend_list_with_availability()
    mode = onebot_list_listing_mode(fetch_status)
    if mode == "empty":
        return RustRconUserPolicyListResponse(
            users=[],
            friend_list_available=False,
        )
    users = _message_enabled_users(snap, friends)
    return RustRconUserPolicyListResponse(
        users=build_user_policy_items(
            snap,
            users,
            include_configured_non_friends=(mode == "map"),
        ),
        friend_list_available=(mode == "map"),
    )


@router.get("/groups", response_model=RustRconGroupPolicyListResponse)
async def list_group_policies(_: AdminUser):
    svc = get_config_service()
    return await _list_group_policy_response(svc.get_snapshot())


@router.put("/groups/{group_id}", response_model=RustRconGroupPolicyMutationResponse)
async def update_group_policy(
    group_id: str,
    body: RustRconGroupPolicyUpdateRequest,
    _: AdminUser,
):
    await _ensure_group_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)

    if not body.enabled:
        await svc.delete_rust_rcon_group_policy(group_id)
    else:
        await svc.upsert_rust_rcon_group_policy(group_id, enabled=True)
    await svc.reload()

    snap = svc.get_snapshot()
    group = await _group_meta(group_id)
    return RustRconGroupPolicyMutationResponse(
        item=build_group_policy_item(snap, group),
    )


@router.delete(
    "/groups/{group_id}", response_model=RustRconGroupPolicyMutationResponse
)
async def reset_group_policy(group_id: str, _: AdminUser):
    await _ensure_group_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_group_message_enabled(group_id, snap)
    await svc.delete_rust_rcon_group_policy(group_id)
    await svc.reload()

    snap = svc.get_snapshot()
    group = await _group_meta(group_id)
    return RustRconGroupPolicyMutationResponse(
        item=build_group_policy_item(snap, group),
    )


@router.get("/users", response_model=RustRconUserPolicyListResponse)
async def list_user_policies(_: AdminUser):
    svc = get_config_service()
    return await _list_user_policy_response(svc.get_snapshot(), refresh_users=True)


@router.put("/users/{user_id}", response_model=RustRconUserPolicyMutationResponse)
async def update_user_policy(
    user_id: str,
    body: RustRconUserPolicyUpdateRequest,
    _: AdminUser,
):
    await _ensure_friend_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_private_message_enabled(user_id, snap)
    existing = snap.rust_rcon_user_policies.get(str(user_id).strip())

    if not body.enabled:
        await svc.delete_rust_rcon_user_policy(user_id)
    else:
        await svc.upsert_rust_rcon_user_policy(
            user_id,
            enabled=True,
            name=body.name
            if body.name is not None
            else (existing.name if existing else None),
        )
    await svc.reload()

    snap = svc.get_snapshot()
    users = await get_friend_list()
    user = next(
        (item for item in users if str(item["user_id"]) == str(user_id)),
        {"user_id": str(user_id), "nickname": body.name},
    )
    return RustRconUserPolicyMutationResponse(
        item=build_user_policy_item(snap, user),
    )


@router.delete("/users/{user_id}", response_model=RustRconUserPolicyMutationResponse)
async def reset_user_policy(user_id: str, _: AdminUser):
    await _ensure_friend_list_complete_for_mutation()
    svc = get_config_service()
    snap = svc.get_snapshot()
    _ensure_private_message_enabled(user_id, snap)
    await svc.delete_rust_rcon_user_policy(user_id)
    await svc.reload()

    snap = svc.get_snapshot()
    users = await get_friend_list()
    user = next(
        (item for item in users if str(item["user_id"]) == str(user_id)),
        {"user_id": str(user_id)},
    )
    return RustRconUserPolicyMutationResponse(
        item=build_user_policy_item(snap, user),
    )
