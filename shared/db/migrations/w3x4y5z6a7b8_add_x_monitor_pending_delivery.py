"""add pending delivery fields to X monitor state

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-08-10 14:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "w3x4y5z6a7b8"
down_revision: str | Sequence[str] | None = "v2w3x4y5z6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.add_column(
        "shared_db_xmonitorstate",
        sa.Column("pending_tweet_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "shared_db_xmonitorstate",
        sa.Column(
            "pending_group_ids",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "shared_db_xmonitorstate",
        sa.Column(
            "pending_user_ids",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_column("shared_db_xmonitorstate", "pending_user_ids")
    op.drop_column("shared_db_xmonitorstate", "pending_group_ids")
    op.drop_column("shared_db_xmonitorstate", "pending_tweet_id")
