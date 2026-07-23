"""Database operations for Rust shop items and point redemption."""

from __future__ import annotations

import math
from dataclasses import dataclass

from nonebot_plugin_orm import get_session
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from shared.config.rust_player import (
    normalize_shop_item_id,
    normalize_shop_item_name,
    normalize_shop_points_cost,
    normalize_shop_quantity,
)
from shared.db.models import RustPlayerPoints, RustShopItem

SHOP_LIST_PAGE_SIZE = 20


@dataclass(frozen=True)
class ShopListPage:
    items: list[RustShopItem]
    page: int
    total_pages: int
    total_items: int
    page_size: int = SHOP_LIST_PAGE_SIZE


async def _detach_shop_item(session, row: RustShopItem) -> RustShopItem:
    await session.refresh(row)
    session.expunge(row)
    return row


async def list_shop_items(*, enabled_only: bool = False) -> list[RustShopItem]:
    async with get_session() as session:
        async with session.begin():
            stmt = select(RustShopItem).order_by(
                RustShopItem.sort_order, RustShopItem.id
            )
            if enabled_only:
                stmt = stmt.where(RustShopItem.enabled.is_(True))
            rows = (await session.scalars(stmt)).all()
            return [await _detach_shop_item(session, row) for row in rows]


async def get_shop_list_page(page: int, *, enabled_only: bool = True) -> ShopListPage:
    page = max(1, int(page))
    async with get_session() as session:
        async with session.begin():
            stmt = select(RustShopItem).order_by(
                RustShopItem.sort_order, RustShopItem.id
            )
            if enabled_only:
                stmt = stmt.where(RustShopItem.enabled.is_(True))
            rows = (await session.scalars(stmt)).all()
            total_items = len(rows)
            total_pages = max(1, math.ceil(total_items / SHOP_LIST_PAGE_SIZE))
            if page > total_pages:
                page = total_pages
            start = (page - 1) * SHOP_LIST_PAGE_SIZE
            end = start + SHOP_LIST_PAGE_SIZE
            page_rows = rows[start:end]
            return ShopListPage(
                items=[await _detach_shop_item(session, row) for row in page_rows],
                page=page,
                total_pages=total_pages,
                total_items=total_items,
            )


async def get_shop_item(shop_id: int) -> RustShopItem | None:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(RustShopItem, int(shop_id))
            if row is None:
                return None
            return await _detach_shop_item(session, row)


async def find_shop_item_by_identifier(identifier: str) -> RustShopItem | None:
    key = str(identifier).strip()
    if not key:
        return None
    async with get_session() as session:
        async with session.begin():
            by_item_id = await session.scalar(
                select(RustShopItem).where(
                    RustShopItem.item_id == key,
                    RustShopItem.enabled.is_(True),
                )
            )
            if by_item_id is not None:
                return await _detach_shop_item(session, by_item_id)
            by_name_rows = (
                await session.scalars(
                    select(RustShopItem).where(
                        RustShopItem.name == key,
                        RustShopItem.enabled.is_(True),
                    )
                )
            ).all()
            if len(by_name_rows) > 1:
                raise ValueError("存在多个同名商品，请使用物品 ID 兑换")
            if len(by_name_rows) == 1:
                return await _detach_shop_item(session, by_name_rows[0])
            return None


async def _enabled_name_taken(
    session, name: str, *, exclude_id: int | None = None
) -> bool:
    stmt = select(RustShopItem.id).where(
        RustShopItem.name == name,
        RustShopItem.enabled.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(RustShopItem.id != exclude_id)
    return (await session.scalar(stmt.limit(1))) is not None


async def create_shop_item(
    *,
    name: str,
    item_id: str,
    points_cost: int,
    enabled: bool = True,
    sort_order: int = 0,
) -> RustShopItem:
    name = normalize_shop_item_name(name)
    item_id = normalize_shop_item_id(item_id)
    points_cost = normalize_shop_points_cost(points_cost)
    sort_order = int(sort_order)
    async with get_session() as session:
        async with session.begin():
            if enabled and await _enabled_name_taken(session, name):
                raise ValueError("已存在同名的启用商品")
            row = RustShopItem(
                name=name,
                item_id=item_id,
                points_cost=points_cost,
                enabled=bool(enabled),
                sort_order=sort_order,
            )
            session.add(row)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise ValueError("物品 ID 已存在") from exc
            return await _detach_shop_item(session, row)


async def update_shop_item(
    shop_id: int,
    *,
    name: str | None = None,
    item_id: str | None = None,
    points_cost: int | None = None,
    enabled: bool | None = None,
    sort_order: int | None = None,
) -> RustShopItem:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(RustShopItem, int(shop_id))
            if row is None:
                raise ValueError("商品不存在")
            next_name = normalize_shop_item_name(name) if name is not None else row.name
            next_enabled = bool(enabled) if enabled is not None else row.enabled
            if next_enabled and await _enabled_name_taken(
                session, next_name, exclude_id=row.id
            ):
                raise ValueError("已存在同名的启用商品")
            if name is not None:
                row.name = next_name
            if item_id is not None:
                row.item_id = normalize_shop_item_id(item_id)
            if points_cost is not None:
                row.points_cost = normalize_shop_points_cost(points_cost)
            if enabled is not None:
                row.enabled = bool(enabled)
            if sort_order is not None:
                row.sort_order = int(sort_order)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise ValueError("物品 ID 已存在") from exc
            return await _detach_shop_item(session, row)


async def delete_shop_item(shop_id: int) -> bool:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(RustShopItem, int(shop_id))
            if row is None:
                return False
            await session.delete(row)
            return True


async def deduct_group_points(group_id: str, user_id: str, amount: int) -> int:
    """Deduct points with a conditional UPDATE. Returns remaining balance."""
    amount = int(amount)
    if amount <= 0:
        raise ValueError("扣除积分必须为正数")
    group_id = str(group_id).strip()
    user_id = str(user_id).strip()
    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                update(RustPlayerPoints)
                .where(
                    RustPlayerPoints.group_id == group_id,
                    RustPlayerPoints.user_id == user_id,
                    RustPlayerPoints.points >= amount,
                )
                .values(points=RustPlayerPoints.points - amount)
            )
            if result.rowcount == 1:
                row = await session.get(
                    RustPlayerPoints,
                    {"group_id": group_id, "user_id": user_id},
                )
                assert row is not None
                return row.points
            row = await session.get(
                RustPlayerPoints,
                {"group_id": group_id, "user_id": user_id},
            )
            current = row.points if row is not None else 0
            raise ValueError(f"积分不足，需要 {amount} 积分，当前 {current} 积分")


async def add_group_points(group_id: str, user_id: str, amount: int) -> int:
    """Add points with a conditional UPDATE. Returns new balance."""
    amount = int(amount)
    if amount <= 0:
        raise ValueError("增加积分必须为正数")
    group_id = str(group_id).strip()
    user_id = str(user_id).strip()
    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                update(RustPlayerPoints)
                .where(
                    RustPlayerPoints.group_id == group_id,
                    RustPlayerPoints.user_id == user_id,
                )
                .values(points=RustPlayerPoints.points + amount)
            )
            if result.rowcount == 1:
                row = await session.get(
                    RustPlayerPoints,
                    {"group_id": group_id, "user_id": user_id},
                )
                assert row is not None
                return row.points
            row = RustPlayerPoints(group_id=group_id, user_id=user_id, points=amount)
            session.add(row)
            await session.flush()
            return row.points


@dataclass(frozen=True)
class RedeemResult:
    item: RustShopItem
    quantity: int
    total_cost: int
    remaining_points: int


async def redeem_shop_item(
    group_id: str,
    user_id: str,
    identifier: str,
    quantity: int,
) -> RedeemResult:
    quantity = normalize_shop_quantity(quantity)
    item = await find_shop_item_by_identifier(identifier)
    if item is None:
        raise ValueError("未找到该商品，请检查物品 ID 或商品中文名")
    total_cost = item.points_cost * quantity
    remaining = await deduct_group_points(group_id, user_id, total_cost)
    return RedeemResult(
        item=item,
        quantity=quantity,
        total_cost=total_cost,
        remaining_points=remaining,
    )
