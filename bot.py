import logging
import os
import pkgutil
import sys
from pathlib import Path

import nonebot
from nonebot.adapters.console import Adapter as ConsoleAdapter  # 避免重复命名
from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter  # 添加OneBot适配器
from nonebot.log import LoguruHandler, logger

# 启动时记录仍通过环境变量生效的配置
_SECRET_ENV_VARS = frozenset({"WEB_SECRET_KEY"})
_OBSOLETE_ENV_EXACT = frozenset({"NOTIFY_GROUPS", "BILIBILI_COOKIE", "SUPERUSERS"})
_OBSOLETE_ENV_PREFIXES = (
    "DYNAMIC_MONITOR_",
    "LIVE_MONITOR_",
    "STATUS_CHECK_",
)


def _detect_runtime() -> str:
    if any(key.startswith(("KUBERNETES_", "KUBE_")) for key in os.environ):
        return "Kubernetes"
    if os.getenv("DOCKER_CONTAINER", "").lower() == "true" or os.path.exists(
        "/.dockerenv"
    ):
        return "Docker"
    return "本地"


def _format_env_value(key: str, value: str | None) -> str:
    if value is None or not str(value).strip():
        return "(未设置)"
    if key in _SECRET_ENV_VARS:
        return "(已设置)" if value.strip() else "(未设置)"
    if key == "SQLALCHEMY_DATABASE_URL":
        return _mask_database_url(value)
    return value


def _mask_database_url(url: str) -> str:
    """Hide credentials in database URLs while keeping engine/host/db name visible."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, host_part = rest.rsplit("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return f"{scheme}://{user}:***@{host_part}"
            return f"{scheme}://***@{host_part}"
    return url


def _collect_obsolete_env_vars() -> list[str]:
    obsolete: list[str] = []
    for key in os.environ:
        if key in _OBSOLETE_ENV_EXACT:
            obsolete.append(key)
        elif any(key.startswith(prefix) for prefix in _OBSOLETE_ENV_PREFIXES):
            obsolete.append(key)
    return sorted(obsolete)


def log_startup_config() -> None:
    """Log environment variables that still affect runtime; plugin config lives in Web Admin."""
    runtime = _detect_runtime()
    logger.info("运行环境: {}", runtime)

    env_file = Path(".env")
    if runtime == "本地" and env_file.exists():
        logger.info("本地配置文件: {}", env_file.resolve())

    startup_vars = {
        "NoneBot": ["HOST", "PORT", "COMMAND_START", "COMMAND_SEP", "LOG_LEVEL"],
        "日志文件": [
            "LOG_FILE_ENABLED",
            "LOG_FILE_PATH",
            "LOG_FILE_LEVEL",
            "LOG_FILE_ROTATION",
            "LOG_FILE_RETENTION",
        ],
        "Web Admin": ["WEB_HOST", "WEB_PORT", "WEB_ADMIN_ENABLED", "WEB_SECRET_KEY"],
        "数据库": ["SQLALCHEMY_DATABASE_URL"],
        "构建信息": [
            "GIT_TAG",
            "GIT_BRANCH",
            "GIT_COMMIT",
            "BUILD_TIME",
            "BUILD_VERSION",
        ],
    }

    for category, keys in startup_vars.items():
        items = [f"{key}={_format_env_value(key, os.getenv(key))}" for key in keys]
        logger.info("{}: {}", category, " | ".join(items))

    obsolete = _collect_obsolete_env_vars()
    if obsolete:
        logger.warning(
            "检测到已弃用的环境变量（不再生效，请在 Web Admin 中配置）: "
            + ", ".join(obsolete)
        )

    logger.info("业务配置（监控、Cookie、模板、权限等）由 Web Admin / 数据库管理")


def _install_stdlib_log_bridge() -> None:
    """Bridge stdlib logging into the NoneBot/loguru pipeline."""
    root = logging.getLogger()
    root.handlers = [LoguruHandler()]
    root.setLevel(logging.DEBUG)


def configure_logging() -> None:
    """Tune noisy third-party stdlib loggers.

    LOG_LEVEL is read by NoneBot during nonebot.init() and controls terminal
    output only; this does not change nonebot.log.logger filtering.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if log_level == "DEBUG":
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("playwright").setLevel(logging.WARNING)
    else:
        logging.getLogger("aiohttp").setLevel(logging.ERROR)
        logging.getLogger("playwright").setLevel(logging.ERROR)


def _ensure_sqlite_parent_dir(url: str) -> None:
    """为相对路径的 SQLite 数据库自动创建父目录（如 data/）。"""
    if not url.lower().startswith("sqlite") or "///" not in url:
        return
    db_part = url.split("///", 1)[1].split("?", 1)[0]
    if not db_part or db_part == ":memory:":
        return
    db_path = Path(db_part)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _configure_alembic_auto_upgrade() -> None:
    """启动时自动执行 Alembic upgrade，不弹出人工确认。"""
    import click

    _confirm = click.confirm

    def _auto_confirm(message: str, *args, **kwargs) -> bool:
        if "迁移" in message:
            return True
        return _confirm(message, *args, **kwargs)

    click.confirm = _auto_confirm  # type: ignore[method-assign]


# 尽早加载 .env（供 SQLALCHEMY_DATABASE_URL、WEB_SECRET_KEY 等使用）
_env_path = Path(".env")
if _env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_path)
    except ImportError:
        pass

# 默认 SQLite 路径（与 env.example 一致）
if not os.getenv("SQLALCHEMY_DATABASE_URL"):
    os.environ["SQLALCHEMY_DATABASE_URL"] = "sqlite+aiosqlite:///data/cyxcbot.db"

_db_url = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///data/cyxcbot.db")
_ensure_sqlite_parent_dir(_db_url)
_app_base = (
    Path(sys._MEIPASS)
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
_migrations_dir = _app_base / "shared" / "db" / "migrations"

from shared.db.alembic_repair import repair_alembic_version_if_needed

repair_alembic_version_if_needed(_db_url)
_configure_alembic_auto_upgrade()

# 初始化 NoneBot
# alembic_startup_check=True：通过 Alembic upgrade 应用 migrations/ 中的迁移。
# 勿用 False（sync）：模型与库不一致且 autogenerate 失败时会回退为删表重建，导致数据丢失。
nonebot.init(
    sqlalchemy_database_url=_db_url,
    alembic_startup_check=True,
    alembic_version_locations=_migrations_dir,
)

nonebot.load_plugin("nonebot_plugin_orm")
import admin.startup  # noqa: F401
import shared.db.models  # noqa: F401

_install_stdlib_log_bridge()
configure_logging()
logger.info("日志级别: {}", os.getenv("LOG_LEVEL", "INFO").upper())

from shared.logging.broadcast import install_log_broadcast
from shared.logging.file_sink import install_file_log_sink

install_log_broadcast()
install_file_log_sink()

# 记录启动配置（在 NoneBot 初始化之后）
log_startup_config()

# 配置控制台适配器为无头模式
nonebot.get_driver().config.console_headless_mode = True

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(ConsoleAdapter)
driver.register_adapter(OneBotAdapter)

# 加载插件
try:
    nonebot.load_builtin_plugins("echo")  # 内置插件
    if getattr(sys, "frozen", False):
        # PyInstaller 下插件在 _MEIPASS/plugins；load_plugins(绝对路径) 会被
        # nonebot 相对 CWD 转成 _internal.plugins.*，故按模块名显式加载。
        _plugins_dir = Path(sys._MEIPASS) / "plugins"
        for _module in pkgutil.iter_modules([str(_plugins_dir)]):
            if not _module.name.startswith("_"):
                nonebot.load_plugin(f"plugins.{_module.name}")
    else:
        nonebot.load_plugins("plugins")
    logger.info("插件加载完成")
except Exception:
    logger.opt(exception=True).error("插件加载失败")
    raise

if __name__ == "__main__":
    nonebot.run()
