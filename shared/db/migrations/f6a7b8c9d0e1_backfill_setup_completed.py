"""backfill setup completed marker for existing installations

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-12 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETUP_KEY = "__setup_completed__"


def upgrade(name: str = "") -> None:
    if name:
        return

    op.execute(
        sa.text(
            "INSERT INTO shared_db_systemsetting (key, value, updated_at) "
            "SELECT :setup_key, '1', CURRENT_TIMESTAMP "
            "WHERE EXISTS (SELECT 1 FROM shared_db_user) "
            "AND NOT EXISTS ("
            "SELECT 1 FROM shared_db_systemsetting WHERE key = :setup_key"
            ")"
        ).bindparams(setup_key=_SETUP_KEY)
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.execute(
        sa.text(
            "DELETE FROM shared_db_systemsetting WHERE key = :setup_key"
        ).bindparams(setup_key=_SETUP_KEY)
    )
