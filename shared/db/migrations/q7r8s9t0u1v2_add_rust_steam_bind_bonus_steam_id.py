"""add steam_id to rust steam bind bonus awarded

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-07-24 11:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q7r8s9t0u1v2"
down_revision: str | Sequence[str] | None = "p6q7r8s9t0u1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.add_column(
        "shared_db_ruststeambindbonusawarded",
        sa.Column("steam_id", sa.String(length=20), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE shared_db_ruststeambindbonusawarded
            SET steam_id = (
                SELECT steam_id
                FROM shared_db_ruststeambinding
                WHERE shared_db_ruststeambinding.user_id
                    = shared_db_ruststeambindbonusawarded.user_id
            )
            """
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM shared_db_ruststeambindbonusawarded WHERE steam_id IS NULL"
        )
    )
    with op.batch_alter_table("shared_db_ruststeambindbonusawarded") as batch_op:
        batch_op.alter_column("steam_id", nullable=False)
        batch_op.create_unique_constraint(
            "uq_rust_steam_bind_bonus_steam_id",
            ["steam_id"],
        )


def downgrade(name: str = "") -> None:
    if name:
        return

    with op.batch_alter_table("shared_db_ruststeambindbonusawarded") as batch_op:
        batch_op.drop_constraint(
            "uq_rust_steam_bind_bonus_steam_id",
            type_="unique",
        )
        batch_op.drop_column("steam_id")
