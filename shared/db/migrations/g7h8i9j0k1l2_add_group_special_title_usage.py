"""add group special title daily usage table

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-03 18:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_groupspecialtitleusage",
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("usage_date", sa.String(length=10), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("group_id", "user_id", "usage_date"),
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("shared_db_groupspecialtitleusage")
