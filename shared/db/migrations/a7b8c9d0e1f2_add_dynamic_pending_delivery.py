"""persist pending dynamic notification delivery

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-10-07 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "z6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    op.add_column(
        "shared_db_dynamicmonitorstate",
        sa.Column("pending_deliveries", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade(name: str = "") -> None:
    if name:
        return
    op.drop_column("shared_db_dynamicmonitorstate", "pending_deliveries")
