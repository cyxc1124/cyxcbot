"""initial shared schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-08 16:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("shared.db",)
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "shared_db_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_user")),
        sa.UniqueConstraint("username", name=op.f("uq_shared_db_user_username")),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_systemsetting",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_shared_db_systemsetting")),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_dynamictarget",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_dynamictarget")),
        sa.UniqueConstraint("uid", name=op.f("uq_shared_db_dynamictarget_uid")),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_dynamictargetgroup",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dynamic_target_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["dynamic_target_id"],
            ["shared_db_dynamictarget.id"],
            name=op.f("fk_shared_db_dynamictargetgroup_dynamic_target_id_shared_db_dynamictarget"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_dynamictargetgroup")),
        sa.UniqueConstraint("dynamic_target_id", "group_id", name="uq_dynamic_target_group"),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_livetarget",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_livetarget")),
        sa.UniqueConstraint("room_id", name=op.f("uq_shared_db_livetarget_room_id")),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_livetargetgroup",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("live_target_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["live_target_id"],
            ["shared_db_livetarget.id"],
            name=op.f("fk_shared_db_livetargetgroup_live_target_id_shared_db_livetarget"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_livetargetgroup")),
        sa.UniqueConstraint("live_target_id", "group_id", name="uq_live_target_group"),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_dynamicmonitorstate",
        sa.Column("uid", sa.String(length=32), nullable=False),
        sa.Column("last_dynamic_id", sa.Integer(), nullable=False),
        sa.Column("initialized", sa.Boolean(), nullable=False),
        sa.Column("pinned_dynamic_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("uid", name=op.f("pk_shared_db_dynamicmonitorstate")),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_livemonitorstate",
        sa.Column("room_id", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("start_time", sa.Integer(), nullable=True),
        sa.Column("streamer_name", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("room_id", name=op.f("pk_shared_db_livemonitorstate")),
        info={"bind_key": "shared.db"},
    )
    op.create_table(
        "shared_db_auditlog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_auditlog")),
        info={"bind_key": "shared.db"},
    )
    op.create_index(op.f("ix_shared_db_auditlog_action"), "shared_db_auditlog", ["action"], unique=False)
    op.create_index(op.f("ix_shared_db_auditlog_created_at"), "shared_db_auditlog", ["created_at"], unique=False)
    op.create_table(
        "shared_db_systemevent",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shared_db_systemevent")),
        info={"bind_key": "shared.db"},
    )
    op.create_index(op.f("ix_shared_db_systemevent_event_type"), "shared_db_systemevent", ["event_type"], unique=False)
    op.create_index(op.f("ix_shared_db_systemevent_created_at"), "shared_db_systemevent", ["created_at"], unique=False)


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_index(op.f("ix_shared_db_systemevent_created_at"), table_name="shared_db_systemevent")
    op.drop_index(op.f("ix_shared_db_systemevent_event_type"), table_name="shared_db_systemevent")
    op.drop_table("shared_db_systemevent")
    op.drop_index(op.f("ix_shared_db_auditlog_created_at"), table_name="shared_db_auditlog")
    op.drop_index(op.f("ix_shared_db_auditlog_action"), table_name="shared_db_auditlog")
    op.drop_table("shared_db_auditlog")
    op.drop_table("shared_db_livemonitorstate")
    op.drop_table("shared_db_dynamicmonitorstate")
    op.drop_table("shared_db_livetargetgroup")
    op.drop_table("shared_db_livetarget")
    op.drop_table("shared_db_dynamictargetgroup")
    op.drop_table("shared_db_dynamictarget")
    op.drop_table("shared_db_systemsetting")
    op.drop_table("shared_db_user")
