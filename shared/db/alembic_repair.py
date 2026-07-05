"""Recover alembic_version after sync-mode schema drift."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from nonebot.log import logger
from sqlalchemy import Connection, Inspector, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from shared.security.database_url import mask_database_url

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

_SYNC_URL_PREFIXES = (
    ("sqlite+aiosqlite", "sqlite"),
    ("postgresql+asyncpg", "postgresql+psycopg"),
    ("mysql+aiomysql", "mysql+pymysql"),
    ("mysql+asyncmy", "mysql+pymysql"),
)

_ASYNC_URL_PREFIXES = (
    "postgresql+asyncpg",
    "mysql+aiomysql",
    "mysql+asyncmy",
)


class SchemaProbe(Protocol):
    def table_exists(self, table: str) -> bool: ...

    def column_exists(self, table: str, column: str) -> bool: ...


class _InspectorProbe:
    def __init__(self, inspector: Inspector) -> None:
        self._inspector = inspector

    def table_exists(self, table: str) -> bool:
        return table in self._inspector.get_table_names()

    def column_exists(self, table: str, column: str) -> bool:
        if not self.table_exists(table):
            return False
        return column in {col["name"] for col in self._inspector.get_columns(table)}


def sync_database_url(url: str) -> str:
    """Map async SQLAlchemy URLs to sync drivers for startup repair."""
    for async_prefix, sync_prefix in _SYNC_URL_PREFIXES:
        if url.startswith(f"{async_prefix}:"):
            return f"{sync_prefix}:{url[len(async_prefix) + 1 :]}"
    return url


def repair_url_candidates(url: str) -> list[tuple[str, bool]]:
    """Return (engine_url, use_async_engine) pairs in preference order."""
    if url.startswith("sqlite+aiosqlite:"):
        return [(sync_database_url(url), False)]
    sync_mapped = sync_database_url(url)
    if any(url.startswith(f"{prefix}:") for prefix in _ASYNC_URL_PREFIXES):
        candidates: list[tuple[str, bool]] = [(url, True)]
        if sync_mapped != url:
            candidates.append((sync_mapped, False))
        return candidates
    return [(url, False)]


def _sqlite_file_missing(sync_url: str) -> bool:
    if not sync_url.startswith("sqlite:///"):
        return False
    db_part = sync_url.removeprefix("sqlite:///").split("?", 1)[0]
    if not db_part or db_part == ":memory:":
        return True
    db_path = Path(db_part)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    return not db_path.is_file()


def _alembic_revision_index(revision: str) -> int:
    return _ALEMBIC_REVISION_ORDER.index(revision)


def infer_alembic_revision(probe: SchemaProbe) -> str:
    """Infer alembic head from existing schema (recover from sync mode)."""
    if probe.column_exists("shared_db_linkparsergrouppolicy", "dynamic_enabled"):
        return "h8i9j0k1l2m3"
    if probe.table_exists("shared_db_groupspecialtitleusage"):
        return "g7h8i9j0k1l2"
    if probe.table_exists("shared_db_dynamictargetuser") and not probe.table_exists(
        "shared_db_auditlog"
    ):
        return "e5f6a7b8c9d0"
    if probe.table_exists("shared_db_dynamictargetuser"):
        return "d4e5f6a7b8c9"
    if probe.table_exists("shared_db_linkparsergrouppolicy"):
        return "c3d4e5f6a7b8"
    if probe.column_exists("shared_db_dynamictarget", "at_all"):
        return "b2c3d4e5f6a7"
    return "a1b2c3d4e5f6"


def _apply_repair_on_connection(
    conn: Connection, probe: _InspectorProbe, inferred: str
) -> None:
    if not probe.table_exists("alembic_version"):
        conn.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
    current = conn.execute(
        text("SELECT version_num FROM alembic_version LIMIT 1")
    ).first()
    if current is None:
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": inferred},
        )
        logger.warning(
            "alembic_version 为空但库表已存在，已自动标记为 {}",
            inferred,
        )
        return

    current_revision = str(current[0])
    if _alembic_revision_index(current_revision) < _alembic_revision_index(inferred):
        conn.execute(
            text("UPDATE alembic_version SET version_num = :revision"),
            {"revision": inferred},
        )
        logger.warning(
            "alembic_version={} 落后于现有 schema，已自动标记为 {}",
            current_revision,
            inferred,
        )


def _run_repair_on_connection(conn: Connection) -> None:
    probe = _InspectorProbe(inspect(conn))
    if not probe.table_exists("shared_db_user"):
        return
    inferred = infer_alembic_revision(probe)
    _apply_repair_on_connection(conn, probe, inferred)


def _repair_sync(url: str) -> None:
    engine: Engine | None = None
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.begin() as conn:
            _run_repair_on_connection(conn)
    finally:
        if engine is not None:
            engine.dispose()


async def _repair_async(url: str) -> None:
    engine: AsyncEngine | None = None
    try:
        engine = create_async_engine(url, pool_pre_ping=True)
        async with engine.begin() as conn:
            await conn.run_sync(_run_repair_on_connection)
    finally:
        if engine is not None:
            await engine.dispose()


def repair_alembic_version_if_needed(url: str) -> None:
    """sync 模式可能留下表但清空 alembic_version；补齐版本号以便 upgrade 不重复建表。"""
    sync_url = sync_database_url(url)
    if _sqlite_file_missing(sync_url):
        return

    candidates = repair_url_candidates(url)
    for index, (candidate_url, use_async) in enumerate(candidates):
        try:
            if use_async:
                asyncio.run(_repair_async(candidate_url))
            else:
                _repair_sync(candidate_url)
            return
        except (ImportError, ModuleNotFoundError, SQLAlchemyError) as exc:
            is_last = index == len(candidates) - 1
            if is_last:
                logger.opt(exception=True).warning(
                    "无法连接数据库或修复 alembic_version（最后尝试 {}），跳过自动标记: {}",
                    mask_database_url(candidate_url),
                    exc,
                )
            else:
                logger.debug(
                    "alembic repair 使用 {} 失败，尝试下一种连接方式: {}",
                    mask_database_url(candidate_url),
                    exc,
                )


# ponytail: URL 归一化仅覆盖文档/Helm 中的常见写法
assert sync_database_url("sqlite+aiosqlite:///data/cyxcbot.db") == (
    "sqlite:///data/cyxcbot.db"
)
assert sync_database_url("postgresql+asyncpg://u:p@h/db") == (
    "postgresql+psycopg://u:p@h/db"
)
assert repair_url_candidates("postgresql+asyncpg://u:p@h/db") == [
    ("postgresql+asyncpg://u:p@h/db", True),
    ("postgresql+psycopg://u:p@h/db", False),
]
assert repair_url_candidates("postgresql+psycopg://u:p@h/db") == [
    ("postgresql+psycopg://u:p@h/db", False),
]
