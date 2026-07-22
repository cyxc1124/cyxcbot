"""add allowed qq users to rust rcon bindings

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-07-22 11:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k1l2m3n4o5p6"
down_revision: str | Sequence[str] | None = "j0k1l2m3n4o5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_rustrconbindingalloweduser",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("binding_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["shared_db_rustrconbinding.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("binding_id", "user_id", name="uq_rust_rcon_binding_user"),
        info={"bind_key": "shared.db"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table(
        "shared_db_rustrconbindingalloweduser", info={"bind_key": "shared.db"}
    )
