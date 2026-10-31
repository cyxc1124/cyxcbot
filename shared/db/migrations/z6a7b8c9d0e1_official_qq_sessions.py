"""official QQ sessions and widen openid columns

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-09-26 01:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "y5z6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WIDEN = (
    ("shared_db_dynamictargetgroup", "group_id", False),
    ("shared_db_dynamictargetuser", "user_id", False),
    ("shared_db_livetargetgroup", "group_id", False),
    ("shared_db_livetargetuser", "user_id", False),
    ("shared_db_xtargetgroup", "group_id", False),
    ("shared_db_xtargetuser", "user_id", False),
    ("shared_db_linkparsergrouppolicy", "group_id", True),
    ("shared_db_linkparseruserpolicy", "user_id", True),
    ("shared_db_douyinlinkparsergrouppolicy", "group_id", True),
    ("shared_db_douyinlinkparseruserpolicy", "user_id", True),
    ("shared_db_xlinkparsergrouppolicy", "group_id", True),
    ("shared_db_xlinkparseruserpolicy", "user_id", True),
)


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_officialqqsession",
        sa.Column("openid", sa.String(length=64), primary_key=True),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )

    for table, column, _pk in _WIDEN:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.String(length=32),
                type_=sa.String(length=64),
                existing_nullable=False,
            )


def downgrade(name: str = "") -> None:
    if name:
        return

    for table, column, _pk in reversed(_WIDEN):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.String(length=64),
                type_=sa.String(length=32),
                existing_nullable=False,
            )
    op.drop_table("shared_db_officialqqsession")
