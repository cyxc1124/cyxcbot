"""Tests for bot.py alembic version repair helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bot import _infer_alembic_revision, _repair_alembic_version_if_needed


def _create_base_schema(cur: sqlite3.Cursor) -> None:
    cur.executescript(
        """
        CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
        CREATE TABLE shared_db_user (id INTEGER PRIMARY KEY);
        CREATE TABLE shared_db_dynamictarget (id INTEGER PRIMARY KEY, at_all BOOLEAN);
        """
    )


def test_infer_revision_with_dynamic_enabled_column() -> None:
    cur = sqlite3.connect(":memory:").cursor()
    _create_base_schema(cur)
    cur.execute(
        """
        CREATE TABLE shared_db_linkparsergrouppolicy (
            group_id TEXT PRIMARY KEY,
            video_enabled BOOLEAN,
            live_enabled BOOLEAN,
            dynamic_enabled BOOLEAN
        )
        """
    )
    assert _infer_alembic_revision(cur) == "h8i9j0k1l2m3"


def test_repair_updates_stale_alembic_version(tmp_path: Path) -> None:
    db_path = tmp_path / "stale.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    _create_base_schema(cur)
    cur.execute(
        "CREATE TABLE shared_db_dynamictargetuser (id INTEGER PRIMARY KEY)"
    )
    cur.execute(
        "CREATE TABLE shared_db_linkparsergrouppolicy (group_id TEXT PRIMARY KEY)"
    )
    cur.execute(
        "INSERT INTO alembic_version (version_num) VALUES ('c3d4e5f6a7b8')"
    )
    conn.commit()
    conn.close()

    _repair_alembic_version_if_needed(f"sqlite+aiosqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    conn.close()
    assert revision == ("d4e5f6a7b8c9",)


def test_repair_stamps_empty_alembic_version(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    _create_base_schema(cur)
    cur.execute(
        """
        CREATE TABLE shared_db_linkparsergrouppolicy (
            group_id TEXT PRIMARY KEY,
            video_enabled BOOLEAN,
            live_enabled BOOLEAN,
            dynamic_enabled BOOLEAN
        )
        """
    )
    conn.commit()
    conn.close()

    url = f"sqlite+aiosqlite:///{db_path}"
    _repair_alembic_version_if_needed(url)

    conn = sqlite3.connect(db_path)
    revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    conn.close()
    assert revision == ("h8i9j0k1l2m3",)
