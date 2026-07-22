"""add rust rcon group/user policy tables

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-07-22 11:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j0k1l2m3n4o5"
down_revision: str | Sequence[str] | None = "i9j0k1l2m3n4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_rustrcongrouppolicy",
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("group_id"),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_rustrconuserpolicy",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        info={"bind_key": "shared.db"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("shared_db_rustrconuserpolicy", info={"bind_key": "shared.db"})
    op.drop_table("shared_db_rustrcongrouppolicy", info={"bind_key": "shared.db"})
