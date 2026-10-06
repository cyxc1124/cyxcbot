"""空库必须能在当前 Alembic 上从 base 升到 head。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

_MIGRATIONS = Path(__file__).resolve().parents[1] / "shared" / "db" / "migrations"

_ENV_PY = """
from alembic import context
from sqlalchemy import engine_from_config, pool


def run_migrations_online():
    connectable = engine_from_config(
        context.config.get_section(context.config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
"""


def test_sqlite_upgrades_from_empty_to_head(tmp_path: Path) -> None:
    script_dir = tmp_path / "alembic"
    script_dir.mkdir()
    (script_dir / "env.py").write_text(_ENV_PY, encoding="utf-8")
    db_path = tmp_path / "cyxcbot.db"

    cfg = Config()
    cfg.set_main_option("script_location", str(script_dir))
    cfg.set_main_option("version_locations", str(_MIGRATIONS))
    cfg.set_main_option("version_path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(cfg, "head")

    head = ScriptDirectory.from_config(cfg).get_current_head()
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            inspector = inspect(conn)
            dynamic_cols = {
                col["name"] for col in inspector.get_columns("shared_db_dynamictarget")
            }
            live_cols = {
                col["name"] for col in inspector.get_columns("shared_db_livetarget")
            }
    finally:
        engine.dispose()

    assert version == head
    assert "at_all" in dynamic_cols
    assert "at_all" in live_cols
