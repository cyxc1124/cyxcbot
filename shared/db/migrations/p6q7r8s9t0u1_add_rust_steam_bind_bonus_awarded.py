"""add rust steam bind bonus awarded tracking table

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-07-24 10:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p6q7r8s9t0u1"
down_revision: str | Sequence[str] | None = "o5p6q7r8s9t0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_ruststeambindbonusawarded",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("shared_db_ruststeambindbonusawarded")
