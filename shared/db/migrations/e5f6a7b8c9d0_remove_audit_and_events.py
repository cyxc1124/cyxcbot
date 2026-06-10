"""remove audit log and system event tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-10 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.drop_index(
        op.f("ix_shared_db_systemevent_created_at"), table_name="shared_db_systemevent"
    )
    op.drop_index(
        op.f("ix_shared_db_systemevent_event_type"), table_name="shared_db_systemevent"
    )
    op.drop_table("shared_db_systemevent")
    op.drop_index(
        op.f("ix_shared_db_auditlog_created_at"), table_name="shared_db_auditlog"
    )
    op.drop_index(op.f("ix_shared_db_auditlog_action"), table_name="shared_db_auditlog")
    op.drop_table("shared_db_auditlog")
    op.execute(
        sa.text(
            "DELETE FROM shared_db_systemsetting WHERE key IN "
            "('audit_log_retention_days', 'event_retention_days')"
        )
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_auditlog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_auditlog")),
        info={"bind_key": "shared.db"},
    )
    op.create_index(
        op.f("ix_shared_db_auditlog_action"),
        "shared_db_auditlog",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_shared_db_auditlog_created_at"),
        "shared_db_auditlog",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "shared_db_systemevent",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_systemevent")),
        info={"bind_key": "shared.db"},
    )
    op.create_index(
        op.f("ix_shared_db_systemevent_event_type"),
        "shared_db_systemevent",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_shared_db_systemevent_created_at"),
        "shared_db_systemevent",
        ["created_at"],
        unique=False,
    )
