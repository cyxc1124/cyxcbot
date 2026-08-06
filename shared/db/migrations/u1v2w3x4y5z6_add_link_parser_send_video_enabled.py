"""add send_video_enabled to link parser policies

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-08-06 11:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u1v2w3x4y5z6"
down_revision: str | Sequence[str] | None = "t0u1v2w3x4y5"
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
                "send_video_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade(name: str = "") -> None:
    if name:
        return

    for table in (
        "shared_db_linkparseruserpolicy",
        "shared_db_linkparsergrouppolicy",
    ):
        op.drop_column(table, "send_video_enabled")
