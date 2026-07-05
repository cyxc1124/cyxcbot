"""Tests for shared.db.alembic_repair helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text

from shared.db.alembic_repair import (
    _InspectorProbe,
    infer_alembic_revision,
    repair_alembic_version_if_needed,
    repair_url_candidates,
    sync_database_url,
)


def _create_base_schema(conn) -> None:
    conn.execute(
        text(
            "CREATE TABLE alembic_version ("
            "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
    )
    conn.execute(text("CREATE TABLE shared_db_user (id INTEGER PRIMARY KEY)"))
    conn.execute(
        text(
            "CREATE TABLE shared_db_dynamictarget ("
            "id INTEGER PRIMARY KEY, at_all BOOLEAN)"
        )
    )


def test_sync_database_url_maps_async_drivers() -> None:
    assert sync_database_url("mysql+aiomysql://u:p@h/db") == (
        "mysql+pymysql://u:p@h/db"
    )


def test_repair_url_candidates_prefers_async_driver_for_asyncpg() -> None:
    assert repair_url_candidates("postgresql+asyncpg://u:p@h/db") == [
        ("postgresql+asyncpg://u:p@h/db", True),
        ("postgresql+psycopg://u:p@h/db", False),
    ]


def test_repair_falls_back_to_async_when_sync_driver_missing(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "async-fallback.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_base_schema(conn)
    engine.dispose()

    async_url = f"sqlite+aiosqlite:///{db_path}"
    with (
        patch(
            "shared.db.alembic_repair.repair_url_candidates",
            return_value=[
                ("postgresql+psycopg://missing/db", False),
                (async_url, True),
            ],
        ),
        patch(
            "shared.db.alembic_repair._repair_sync",
            side_effect=ModuleNotFoundError("psycopg"),
        ) as sync_repair,
    ):
        repair_alembic_version_if_needed("postgresql+asyncpg://u:p@h/db")

    sync_repair.assert_called_once()
    verify = create_engine(f"sqlite:///{db_path}")
    with verify.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    verify.dispose()
    assert revision == ("b2c3d4e5f6a7",)


def test_infer_revision_with_dynamic_enabled_column() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_base_schema(conn)
        conn.execute(
            text(
                """
                CREATE TABLE shared_db_linkparsergrouppolicy (
                    group_id TEXT PRIMARY KEY,
                    video_enabled BOOLEAN,
                    live_enabled BOOLEAN,
                    dynamic_enabled BOOLEAN
                )
                """
            )
        )
    assert infer_alembic_revision(_InspectorProbe(inspect(engine))) == "h8i9j0k1l2m3"
    engine.dispose()


def test_repair_updates_stale_alembic_version(tmp_path: Path) -> None:
    db_path = tmp_path / "stale.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_base_schema(conn)
        conn.execute(
            text("CREATE TABLE shared_db_dynamictargetuser (id INTEGER PRIMARY KEY)")
        )
        conn.execute(
            text(
                "CREATE TABLE shared_db_linkparsergrouppolicy (group_id TEXT PRIMARY KEY)"
            )
        )
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('c3d4e5f6a7b8')")
        )
    engine.dispose()

    repair_alembic_version_if_needed(f"sqlite+aiosqlite:///{db_path}")

    verify = create_engine(f"sqlite:///{db_path}")
    with verify.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    verify.dispose()
    assert revision == ("e5f6a7b8c9d0",)


def test_repair_stamps_empty_alembic_version(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_base_schema(conn)
        conn.execute(
            text(
                """
                CREATE TABLE shared_db_linkparsergrouppolicy (
                    group_id TEXT PRIMARY KEY,
                    video_enabled BOOLEAN,
                    live_enabled BOOLEAN,
                    dynamic_enabled BOOLEAN
                )
                """
            )
        )
    engine.dispose()

    repair_alembic_version_if_needed(f"sqlite+aiosqlite:///{db_path}")

    verify = create_engine(f"sqlite:///{db_path}")
    with verify.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    verify.dispose()
    assert revision == ("h8i9j0k1l2m3",)


def test_repair_leaves_unknown_alembic_version_untouched(tmp_path: Path) -> None:
    """库被更新版本升级过（版本号本代码未知）时不得崩溃，也不得回改版本号。"""
    db_path = tmp_path / "future.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_base_schema(conn)
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('zz_future_rev')")
        )
    engine.dispose()

    repair_alembic_version_if_needed(f"sqlite+aiosqlite:///{db_path}")

    verify = create_engine(f"sqlite:///{db_path}")
    with verify.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    verify.dispose()
    assert revision == ("zz_future_rev",)


def test_repair_creates_alembic_version_table_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "no-version.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE shared_db_user (id INTEGER PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE shared_db_dynamictarget (id INTEGER PRIMARY KEY, at_all BOOLEAN)"
            )
        )
    engine.dispose()

    repair_alembic_version_if_needed(f"sqlite+aiosqlite:///{db_path}")

    verify = create_engine(f"sqlite:///{db_path}")
    with verify.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    verify.dispose()
    assert revision == ("b2c3d4e5f6a7",)
