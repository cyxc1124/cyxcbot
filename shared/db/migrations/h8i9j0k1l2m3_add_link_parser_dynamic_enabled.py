"""add dynamic_enabled to link parser policies

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-07-06 00:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h8i9j0k1l2m3"
down_revision: str | Sequence[str] | None = "g7h8i9j0k1l2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    for table in (
        "shared_db_linkparsergrouppolicy",
        "shared_db_linkparseruserpolicy",
    ):
        op.add_column(
            table,
            sa.Column(
                "dynamic_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            info={"bind_key": "shared.db"},
        )


def downgrade(name: str = "") -> None:
    if name:
        return

    for table in (
        "shared_db_linkparseruserpolicy",
        "shared_db_linkparsergrouppolicy",
    ):
        op.drop_column(table, "dynamic_enabled", info={"bind_key": "shared.db"})
