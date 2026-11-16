"""move the X outbound proxy into the shared proxy list

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-11-16 12:00:00

旧版只有一个 X 代理（x_proxy_*），OpenAI 图片检测也沿用它。这里把它转为共享代理
列表中的「原 X 代理」，并让 X 与 OpenAI 来源检测继续使用它（仅当原来已启用）。
已加密的密码直接复制，迁移无需 WEB_SECRET_KEY。旧键保留，便于回退到旧版本。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2g3h4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2g3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETTINGS = sa.table(
    "shared_db_systemsetting",
    sa.column("key", sa.String),
    sa.column("value", sa.Text),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
_NEW_KEYS = ("proxies", "x_proxy_id", "ai_image_openai_proxy_id")
_LEGACY_KEYS = (
    "x_proxy_enabled",
    "x_proxy_scheme",
    "x_proxy_host",
    "x_proxy_port",
    "x_proxy_username",
    "x_proxy_password_encrypted",
)
_LEGACY_ID = "legacy-x"


def _legacy_proxy(rows: dict[str, str]) -> tuple[list[dict], str]:
    host = (rows.get("x_proxy_host") or "").strip()
    if not host:
        return [], ""
    scheme = (rows.get("x_proxy_scheme") or "http").strip().lower()
    if scheme not in ("http", "https", "socks5"):
        scheme = "http"
    try:
        port = max(1, min(65535, int(rows.get("x_proxy_port") or 7890)))
    except ValueError:
        port = 7890
    proxy = {
        "id": _LEGACY_ID,
        "name": "原 X 代理",
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": (rows.get("x_proxy_username") or "").strip(),
        "password_encrypted": rows.get("x_proxy_password_encrypted") or "",
    }
    enabled = (rows.get("x_proxy_enabled") or "").lower() in ("1", "true", "yes", "on")
    return [proxy], _LEGACY_ID if enabled else ""


def upgrade(name: str = "") -> None:
    if name:
        return

    bind = op.get_bind()
    rows = dict(
        bind.execute(
            sa.select(_SETTINGS.c.key, _SETTINGS.c.value).where(
                _SETTINGS.c.key.in_(_NEW_KEYS + _LEGACY_KEYS)
            )
        ).all()
    )
    proxies, selected = _legacy_proxy(rows)
    values = {
        "proxies": json.dumps(proxies, ensure_ascii=False),
        "x_proxy_id": selected,
        "ai_image_openai_proxy_id": selected,
    }
    # 只补缺失的键：重复执行（如 alembic_repair 回填旧 revision 后）不会覆盖新设置。
    missing = [key for key in _NEW_KEYS if key not in rows]
    if missing:
        now = datetime.now(timezone.utc)
        op.bulk_insert(
            _SETTINGS,
            [{"key": key, "value": values[key], "updated_at": now} for key in missing],
        )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.execute(_SETTINGS.delete().where(_SETTINGS.c.key.in_(_NEW_KEYS)))
