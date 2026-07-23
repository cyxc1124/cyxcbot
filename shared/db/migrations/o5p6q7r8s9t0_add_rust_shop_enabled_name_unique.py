"""add partial unique index on enabled rust shop item names

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-07-23 22:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o5p6q7r8s9t0"
down_revision: str | Sequence[str] | None = "n4o5p6q7r8s9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_index(
        "uq_rust_shop_enabled_name",
        "shared_db_rustshopitem",
        ["name"],
        unique=True,
        postgresql_where=sa.text("enabled IS TRUE"),
        sqlite_where=sa.text("enabled = 1"),
        info={"bind_key": "shared.db"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_index(
        "uq_rust_shop_enabled_name",
        table_name="shared_db_rustshopitem",
        info={"bind_key": "shared.db"},
    )
