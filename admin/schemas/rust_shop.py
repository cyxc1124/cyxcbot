"""Schemas for Rust shop admin API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from shared.config.rust_player import (
    normalize_shop_item_id,
    normalize_shop_item_name,
    normalize_shop_points_cost,
    normalize_shop_sort_order,
)


class RustShopItemResponse(BaseModel):
    id: int
    name: str
    item_id: str
    points_cost: int
    enabled: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class RustShopItemListResponse(BaseModel):
    items: List[RustShopItemResponse]


class RustShopItemCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    item_id: str = Field(min_length=1, max_length=128)
    points_cost: int
    enabled: bool = True
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_shop_item_name(value)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return normalize_shop_item_id(value)

    @field_validator("points_cost")
    @classmethod
    def validate_points_cost(cls, value: int) -> int:
        return normalize_shop_points_cost(value)

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, value: int) -> int:
        return normalize_shop_sort_order(value)


class RustShopItemUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    item_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    points_cost: Optional[int] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_shop_item_name(value)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_shop_item_id(value)

    @field_validator("points_cost")
    @classmethod
    def validate_points_cost(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        return normalize_shop_points_cost(value)

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        return normalize_shop_sort_order(value)
