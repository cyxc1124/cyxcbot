"""persist pending live notifications

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2g3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    op.add_column(
        "shared_db_livemonitorstate",
        sa.Column(
            "pending_notifications", sa.Text(), nullable=False, server_default="{}"
        ),
    )


def downgrade(name: str = "") -> None:
    if name:
        return
    op.drop_column("shared_db_livemonitorstate", "pending_notifications")
