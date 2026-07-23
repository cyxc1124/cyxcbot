"""Rust shop item CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.rust_shop import (
    RustShopItemCreateRequest,
    RustShopItemListResponse,
    RustShopItemResponse,
    RustShopItemUpdateRequest,
)
from shared.rust_player import shop_store

router = APIRouter(
    prefix="/rust-shop/items",
    tags=["rust-shop"],
    dependencies=[RequireSetup],
)


def _to_response(row) -> RustShopItemResponse:
    return RustShopItemResponse(
        id=row.id,
        name=row.name,
        item_id=row.item_id,
        points_cost=row.points_cost,
        enabled=row.enabled,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=RustShopItemListResponse)
async def list_rust_shop_items(_: AdminUser) -> RustShopItemListResponse:
    items = await shop_store.list_shop_items()
    return RustShopItemListResponse(items=[_to_response(item) for item in items])


@router.post(
    "",
    response_model=RustShopItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rust_shop_item(
    body: RustShopItemCreateRequest,
    _: AdminUser,
) -> RustShopItemResponse:
    try:
        row = await shop_store.create_shop_item(
            name=body.name,
            item_id=body.item_id,
            points_cost=body.points_cost,
            enabled=body.enabled,
            sort_order=body.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(row)


@router.patch("/{shop_id}", response_model=RustShopItemResponse)
async def update_rust_shop_item(
    shop_id: int,
    body: RustShopItemUpdateRequest,
    _: AdminUser,
) -> RustShopItemResponse:
    try:
        row = await shop_store.update_shop_item(
            shop_id,
            name=body.name,
            item_id=body.item_id,
            points_cost=body.points_cost,
            enabled=body.enabled,
            sort_order=body.sort_order,
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "商品不存在"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return _to_response(row)


@router.delete("/{shop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rust_shop_item(shop_id: int, _: AdminUser) -> None:
    deleted = await shop_store.delete_shop_item(shop_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="商品不存在")
