"""add at_all flag to monitor targets

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08 20:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    # Alembic 1.18 起 add_column() 不再接受 **kw，info= 会直接 TypeError。
    # 单库启动用的是 generic env，运行时不靠 bind_key 选库。
    op.add_column(
        "shared_db_dynamictarget",
        sa.Column("at_all", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "shared_db_livetarget",
        sa.Column("at_all", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_column("shared_db_livetarget", "at_all")
    op.drop_column("shared_db_dynamictarget", "at_all")
