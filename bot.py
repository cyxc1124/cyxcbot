import nonebot
import os
import logging
from pathlib import Path
from nonebot.log import logger, LoguruHandler
from nonebot.adapters.console import Adapter as ConsoleAdapter  # 避免重复命名
from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter  # 添加OneBot适配器

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
    if os.getenv("DOCKER_CONTAINER", "").lower() == "true" or os.path.exists("/.dockerenv"):
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
    logger.info(f"运行环境: {runtime}")

    env_file = Path(".env")
    if runtime == "本地" and env_file.exists():
        logger.info(f"本地配置文件: {env_file.resolve()}")

    startup_vars = {
        "NoneBot": ["HOST", "PORT", "COMMAND_START", "COMMAND_SEP", "LOG_LEVEL"],
        "Web Admin": ["WEB_HOST", "WEB_PORT", "WEB_ADMIN_ENABLED", "WEB_SECRET_KEY"],
        "数据库": ["SQLALCHEMY_DATABASE_URL"],
        "构建信息": ["GIT_TAG", "GIT_COMMIT", "BUILD_VERSION"],
    }

    for category, keys in startup_vars.items():
        items = [f"{key}={_format_env_value(key, os.getenv(key))}" for key in keys]
        logger.info(f"{category}: {' | '.join(items)}")

    obsolete = _collect_obsolete_env_vars()
    if obsolete:
        logger.warning(
            "检测到已弃用的环境变量（不再生效，请在 Web Admin 中配置）: "
            + ", ".join(obsolete)
        )

    logger.info("业务配置（监控、Cookie、模板、权限等）由 Web Admin / 数据库管理")

# 配置日志级别
def configure_logging():
    """根据NoneBot最佳实践配置日志级别"""
    # 从环境变量获取日志级别，默认为INFO
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    # 验证日志级别
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level not in valid_levels:
        log_level = 'INFO'

    # 设置标准库日志级别（影响第三方库的日志）
    numeric_level = getattr(logging, log_level)
    logging.getLogger().setLevel(numeric_level)

    # 为特定模块设置更详细的日志级别（如果需要）
    if log_level == 'DEBUG':
        # 在调试模式下，为关键模块启用更详细的日志
        logging.getLogger('aiohttp').setLevel(logging.WARNING)  # 减少aiohttp的噪声
        logging.getLogger('playwright').setLevel(logging.WARNING)  # 减少playwright的噪声
    else:
        # 在生产模式下，减少第三方库的日志
        logging.getLogger('aiohttp').setLevel(logging.ERROR)
        logging.getLogger('playwright').setLevel(logging.ERROR)

    return log_level

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
    Path("data").mkdir(parents=True, exist_ok=True)
    os.environ["SQLALCHEMY_DATABASE_URL"] = "sqlite+aiosqlite:///data/cyxcbot.db"

_db_url = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///data/cyxcbot.db")
_migrations_dir = Path(__file__).resolve().parent / "shared" / "db" / "migrations"

# 初始化 NoneBot
# alembic_startup_check=False：启动时自动同步数据库 schema（建表/更新），无需额外脚本
nonebot.init(
    sqlalchemy_database_url=_db_url,
    alembic_startup_check=False,
    alembic_version_locations=_migrations_dir,
)

nonebot.load_plugin("nonebot_plugin_orm")
import shared.db.models  # noqa: F401
import admin.startup  # noqa: F401

# 配置日志级别
log_level = configure_logging()
logger.info(f"日志级别设置为: {log_level}")

from shared.logging.broadcast import install_log_broadcast

install_log_broadcast()

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
    nonebot.load_plugins("plugins")  # 加载本地插件
    logger.info("插件加载完成")
except Exception as e:
    logger.error(f"插件加载失败: {e}")
    raise

if __name__ == "__main__":
    nonebot.run()