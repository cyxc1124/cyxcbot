"""Recover alembic_version after sync-mode schema drift."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nonebot.log import logger

_ALEMBIC_REVISION_ORDER = (
    "a1b2c3d4e5f6",
    "b2c3d4e5f6a7",
    "c3d4e5f6a7b8",
    "d4e5f6a7b8c9",
    "e5f6a7b8c9d0",
    "f6a7b8c9d0e1",
    "g7h8i9j0k1l2",
    "h8i9j0k1l2m3",
)


def _sqlite_db_path(url: str) -> Path | None:
    if not url.lower().startswith("sqlite") or "///" not in url:
        return None
    db_part = url.split("///", 1)[1].split("?", 1)[0]
    if not db_part or db_part == ":memory:":
        return None
    db_path = Path(db_part)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    return db_path


def _sqlite_table_exists(cur, table: str) -> bool:
    return (
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        is not None
    )


def _sqlite_column_exists(cur, table: str, column: str) -> bool:
    if not _sqlite_table_exists(cur, table):
        return False
    return any(
        row[1] == column
        for row in cur.execute(f"PRAGMA table_info({table})").fetchall()
    )


def _alembic_revision_index(revision: str) -> int:
    return _ALEMBIC_REVISION_ORDER.index(revision)


def infer_alembic_revision(cur) -> str:
    """Infer alembic head from existing schema (recover from sync mode)."""
    if _sqlite_column_exists(cur, "shared_db_linkparsergrouppolicy", "dynamic_enabled"):
        return "h8i9j0k1l2m3"
    if _sqlite_table_exists(cur, "shared_db_groupspecialtitleusage"):
        return "g7h8i9j0k1l2"
    if _sqlite_table_exists(
        cur, "shared_db_dynamictargetuser"
    ) and not _sqlite_table_exists(cur, "shared_db_auditlog"):
        return "e5f6a7b8c9d0"
    if _sqlite_table_exists(cur, "shared_db_dynamictargetuser"):
        return "d4e5f6a7b8c9"
    if _sqlite_table_exists(cur, "shared_db_linkparsergrouppolicy"):
        return "c3d4e5f6a7b8"
    if _sqlite_column_exists(cur, "shared_db_dynamictarget", "at_all"):
        return "b2c3d4e5f6a7"
    return "a1b2c3d4e5f6"


def repair_alembic_version_if_needed(url: str) -> None:
    """sync 模式可能留下表但清空 alembic_version；补齐版本号以便 upgrade 不重复建表。"""
    db_path = _sqlite_db_path(url)
    if db_path is None or not db_path.is_file():
        return

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if not _sqlite_table_exists(cur, "shared_db_user"):
            return
        inferred = infer_alembic_revision(cur)
        current = cur.execute(
            "SELECT version_num FROM alembic_version LIMIT 1"
        ).fetchone()
        if current is None:
            cur.execute(
                "INSERT INTO alembic_version (version_num) VALUES (?)",
                (inferred,),
            )
            conn.commit()
            logger.warning(
                "alembic_version 为空但库表已存在，已自动标记为 {}",
                inferred,
            )
            return

        current_revision = str(current[0])
        if _alembic_revision_index(current_revision) < _alembic_revision_index(
            inferred
        ):
            cur.execute(
                "UPDATE alembic_version SET version_num = ?",
                (inferred,),
            )
            conn.commit()
            logger.warning(
                "alembic_version={} 落后于现有 schema，已自动标记为 {}",
                current_revision,
                inferred,
            )
    finally:
        conn.close()
