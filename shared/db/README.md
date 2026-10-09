# 数据库迁移维护

数据库模型在 [`models.py`](models.py)，Alembic 迁移在 [`migrations/`](migrations/)。启动时由 `bot.py` 的 `nonebot.init(alembic_startup_check=True)` 执行 Alembic **upgrade**；勿改用 sync 模式，模型变更失败时可能删表重建。

## 历史版本修复

启动前 `bot.py` 调用 [`alembic_repair.py`](alembic_repair.py) 的 `repair_alembic_version_if_needed()`，补救历史上 sync 模式（`alembic_startup_check=False`）留下的版本漂移。该模式会建表却把 `alembic_version` 清空，直接切到 upgrade 会因 `CREATE TABLE` 冲突失败。

repair 仅在**核心表已存在、但 `alembic_version` 空或缺失**时，根据现有表结构推断并回填一次 revision；`alembic_version` 非空的健康库一律不动。它按数据库 URL 尝试已安装的同步/异步驱动：`postgresql+asyncpg` 优先 async、再回退 `psycopg`；SQLite 固定用内置 pysqlite。缺驱动时跳过 repair，不阻断启动。

## 新增结构迁移

`infer_alembic_revision()` 的推断基础上限是切换前的 head（`g7h8i9j0k1l2`）：sync 模式切换前的漂移库只会止步于该版本。但若部署被回滚到仍带 `alembic_startup_check=False` 的旧版本并启动过一次，之后新增迁移引入的列/表（如 h8 的 `dynamic_enabled` 列）可能仍留在数据库中，而 `alembic_version` 被再次清空。

因此，新增会改表结构的 migration 时，仍需在 `infer_alembic_revision()` 中登记可唯一识别的表/列特征（参考 h8 分支的写法），否则 Alembic upgrade 可能因重复建表或加列而启动失败。

`alembic_repair.py` 是一次性过渡代码，只有确认所有历史部署都已迁移完毕、`alembic_version` 均已正常后，才可整体删除。
