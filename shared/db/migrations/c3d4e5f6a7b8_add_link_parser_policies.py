"""add link parser group/user policy tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-08 22:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_linkparsergrouppolicy",
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("video_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("live_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("group_id"),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_linkparseruserpolicy",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("video_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("live_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("private_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        info={"bind_key": "shared.db"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("shared_db_linkparseruserpolicy", info={"bind_key": "shared.db"})
    op.drop_table("shared_db_linkparsergrouppolicy", info={"bind_key": "shared.db"})
