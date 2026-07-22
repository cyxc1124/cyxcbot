"""Shared helpers for tests that need real SQLAlchemy / nonebot_plugin_orm."""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from unittest.mock import MagicMock

import nonebot

_NONE_BOT_SQLITE = "sqlite+aiosqlite:///:memory:"
_DB_MODULE_NAMES = (
    "admin.services.setup_guard",
    "shared.db.models",
    "shared.db.base",
    "nonebot_plugin_orm",
)


def shared_sqlite_url() -> str:
    db_id = uuid.uuid4().hex
    return f"sqlite+aiosqlite:///file:{db_id}?mode=memory&cache=shared&uri=true"


def ensure_real_db_modules() -> None:
    existing = sys.modules.get("shared.db.models")
    if existing is not None and not isinstance(existing, MagicMock):
        user = getattr(existing, "User", None)
        if user is not None and not isinstance(user, MagicMock):
            return

    for name in _DB_MODULE_NAMES:
        module = sys.modules.get(name)
        if module is not None and isinstance(module, MagicMock):
            del sys.modules[name]

    os.environ["SQLALCHEMY_DATABASE_URL"] = _NONE_BOT_SQLITE
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url=_NONE_BOT_SQLITE,
            alembic_startup_check=False,
        )

    if "nonebot_plugin_orm" not in sys.modules or isinstance(
        sys.modules["nonebot_plugin_orm"], MagicMock
    ):
        sys.modules.pop("nonebot_plugin_orm", None)
        nonebot.load_plugin("nonebot_plugin_orm")

    import shared.db.base
    import shared.db.models

    importlib.reload(shared.db.base)
    importlib.reload(shared.db.models)

    if "admin.services.setup_guard" in sys.modules:
        importlib.reload(sys.modules["admin.services.setup_guard"])
