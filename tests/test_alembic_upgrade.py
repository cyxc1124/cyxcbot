"""空库必须能在当前 Alembic 上从 base 升到 head。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
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


def _config(tmp_path: Path) -> tuple[Config, Path]:
    script_dir = tmp_path / "alembic"
    script_dir.mkdir()
    (script_dir / "env.py").write_text(_ENV_PY, encoding="utf-8")
    db_path = tmp_path / "cyxcbot.db"

    cfg = Config()
    cfg.set_main_option("script_location", str(script_dir))
    cfg.set_main_option("version_locations", str(_MIGRATIONS))
    cfg.set_main_option("version_path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg, db_path


def test_sqlite_upgrades_from_empty_to_head(tmp_path: Path) -> None:
    cfg, db_path = _config(tmp_path)

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
            tables = set(inspector.get_table_names())
            cache_ddl = conn.execute(
                text(
                    "SELECT sql FROM sqlite_master WHERE name = 'shared_db_aiimagecache'"
                )
            ).scalar_one()
    finally:
        engine.dispose()

    assert version == head
    assert "at_all" in dynamic_cols
    assert "at_all" in live_cols
    assert "shared_db_aiimagecache" in tables
    assert "AUTOINCREMENT" in cache_ddl


def _settings_after_proxy_migration(tmp_path: Path, rows: dict[str, str]) -> dict:
    cfg, db_path = _config(tmp_path)
    command.upgrade(cfg, "b8c9d0e1f2g3")
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            for key, value in rows.items():
                conn.execute(
                    text(
                        "INSERT INTO shared_db_systemsetting (key, value, updated_at) "
                        "VALUES (:key, :value, CURRENT_TIMESTAMP)"
                    ),
                    {"key": key, "value": value},
                )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            return dict(
                conn.execute(
                    text("SELECT key, value FROM shared_db_systemsetting")
                ).all()
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_x_proxy_moves_into_shared_proxies(tmp_path: Path, enabled: str) -> None:
    from shared.config.proxies import load_proxies
    from shared.security.crypto import encrypt_value

    cipher = encrypt_value("p@ss")
    settings = _settings_after_proxy_migration(
        tmp_path,
        {
            "x_proxy_enabled": enabled,
            "x_proxy_scheme": "socks5",
            "x_proxy_host": " proxy.test ",
            "x_proxy_port": "1080",
            "x_proxy_username": "user",
            "x_proxy_password_encrypted": cipher,
        },
    )
    (proxy,) = load_proxies(settings["proxies"])
    assert (proxy.id, proxy.name, proxy.scheme, proxy.host, proxy.port) == (
        "legacy-x",
        "原 X 代理",
        "socks5",
        "proxy.test",
        1080,
    )
    assert (proxy.username, proxy.password) == ("user", "p@ss")
    # 原来启用时 X 与 OpenAI 检测继续走代理，关闭时只保留代理供以后选用。
    selected = "legacy-x" if enabled == "true" else ""
    assert settings["x_proxy_id"] == settings["ai_image_openai_proxy_id"] == selected
    assert settings["x_proxy_host"] == " proxy.test "


def test_proxy_migration_without_legacy_proxy_or_with_new_settings(
    tmp_path: Path,
) -> None:
    settings = _settings_after_proxy_migration(
        tmp_path,
        {
            "x_proxy_enabled": "true",
            "x_proxy_host": "",
            "x_proxy_id": "kept",
        },
    )
    assert json.loads(settings["proxies"]) == []
    assert settings["x_proxy_id"] == "kept"
    assert settings["ai_image_openai_proxy_id"] == ""
