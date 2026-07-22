"""add online_bonus_earned to rust check-in records

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-07-22 17:35:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m3n4o5p6q7r8"
down_revision: str | Sequence[str] | None = "l2m3n4o5p6q7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.add_column(
        "shared_db_rustcheckinrecord",
        sa.Column(
            "online_bonus_earned",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        info={"bind_key": "shared.db"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_column(
        "shared_db_rustcheckinrecord",
        "online_bonus_earned",
        info={"bind_key": "shared.db"},
    )
