"""widen X monitor pending_tweet_id for delivery fingerprints

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-08-10 18:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "y5z6a7b8c9d0"
down_revision: str | Sequence[str] | None = "x4y5z6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    # tweet_id#batch_fingerprint 可能超过原 String(32)
    with op.batch_alter_table("shared_db_xmonitorstate") as batch_op:
        batch_op.alter_column(
            "pending_tweet_id",
            existing_type=sa.String(length=32),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade(name: str = "") -> None:
    if name:
        return

    with op.batch_alter_table("shared_db_xmonitorstate") as batch_op:
        batch_op.alter_column(
            "pending_tweet_id",
            existing_type=sa.String(length=255),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
