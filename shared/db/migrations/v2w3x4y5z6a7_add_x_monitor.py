"""add X (Twitter) monitor tables

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-08-10 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2w3x4y5z6a7"
down_revision: str | Sequence[str] | None = "u1v2w3x4y5z6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_xtarget",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("at_all", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_shared_db_xtarget_username"),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_xtargetgroup",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("x_target_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["x_target_id"],
            ["shared_db_xtarget.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("x_target_id", "group_id", name="uq_x_target_group"),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_xtargetuser",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("x_target_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["x_target_id"],
            ["shared_db_xtarget.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("x_target_id", "user_id", name="uq_x_target_user"),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_xmonitorstate",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column(
            "last_tweet_id",
            sa.String(length=32),
            server_default="0",
            nullable=False,
        ),
        sa.Column("initialized", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("username"),
        info={"bind_key": "shared.db"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("shared_db_xmonitorstate", info={"bind_key": "shared.db"})
    op.drop_table("shared_db_xtargetuser", info={"bind_key": "shared.db"})
    op.drop_table("shared_db_xtargetgroup", info={"bind_key": "shared.db"})
    op.drop_table("shared_db_xtarget", info={"bind_key": "shared.db"})
