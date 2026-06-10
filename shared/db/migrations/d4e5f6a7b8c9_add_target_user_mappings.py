"""add dynamic/live target friend mappings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-08 23:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_dynamictargetuser",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dynamic_target_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["dynamic_target_id"],
            ["shared_db_dynamictarget.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dynamic_target_id", "user_id", name="uq_dynamic_target_user"
        ),
    )
    op.create_table(
        "shared_db_livetargetuser",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("live_target_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["live_target_id"],
            ["shared_db_livetarget.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("live_target_id", "user_id", name="uq_live_target_user"),
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("shared_db_livetargetuser")
    op.drop_table("shared_db_dynamictargetuser")
