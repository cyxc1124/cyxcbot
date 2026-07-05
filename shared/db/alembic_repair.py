"""Recover alembic_version after sync-mode schema drift.

一次性过渡代码：旧版 alembic_startup_check=False（sync 模式）会建表但把
alembic_version 清空，切到 upgrade 模式后首次启动会因 CREATE TABLE 冲突失败。
本模块仅在「表已存在但 alembic_version 空/缺」时回填推断出的 revision，让 Alembic
upgrade 只补差异。alembic_version 非空的健康库一律不动。
待所有历史部署都迁移完毕（alembic_version 均已正常）后，可整体删除本模块。
"""

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


def infer_alembic_revision(probe: SchemaProbe) -> str:
    """按现有表结构推断 sync 漂移库应回填的 revision。

    仅用于「旧 sync 模式遗留：表已建但 alembic_version 为空」的一次性恢复。
    sync 模式只会把库建到切换 alembic_startup_check=True 之前的 head
    （g7h8i9j0k1l2）为止，因此推断上限冻结在 g7；此后新增的迁移不可能出现在
    漂移库中，无需在此登记新分支，交给 Alembic upgrade 应用即可。

    若 alembic_version 被旧 sync 模式再次清空，但 h8 迁移已应用过的列仍在，
    须识别为 h8，否则 upgrade 会重复 ADD COLUMN 导致启动失败。
    """
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


def _run_repair_on_connection(conn: Connection) -> None:
    probe = _InspectorProbe(inspect(conn))
    if not probe.table_exists("shared_db_user"):
        # 全新库（或非本项目库）：交给 Alembic upgrade 正常建表 + stamp head。
        return

    if probe.table_exists("alembic_version"):
        current = conn.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).first()
        if current is not None:
            # 非空即为新代码正常 upgrade 出来的健康库，交给 Alembic，勿覆盖（否则可能降级）。
            return
    else:
        conn.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )

    inferred = infer_alembic_revision(probe)
    conn.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
        {"revision": inferred},
    )
    logger.warning(
        "检测到 sync 模式遗留（表已存在但 alembic_version 为空），已标记为 {}，"
        "后续由 Alembic upgrade 补齐差异",
        inferred,
    )


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
