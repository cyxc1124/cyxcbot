import nonebot
import os
import logging
from pathlib import Path
from nonebot.log import logger, LoguruHandler
from nonebot.adapters.console import Adapter as ConsoleAdapter  # 避免重复命名
from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter  # 添加OneBot适配器

# 记录环境变量配置（用于调试）
def log_environment_config():
    """记录当前环境变量配置到日志"""
    logger.info("环境变量配置信息")

    # 检测运行环境
    is_kubernetes = any(key.startswith(('KUBERNETES_', 'KUBE_')) for key in os.environ)
    is_docker = os.getenv('DOCKER_CONTAINER', '').lower() == 'true' or os.path.exists('/.dockerenv')

    if is_kubernetes:
        logger.info("运行环境: Kubernetes")
        logger.info("配置来源: ConfigMap/环境变量 (K8s)")
    elif is_docker:
        logger.info("运行环境: Docker容器")
        logger.info("配置来源: Docker环境变量")
    else:
        logger.info("运行环境: 本地开发环境")

        # 在本地环境中尝试加载.env文件
        try:
            from dotenv import load_dotenv, dotenv_values
            env_file = Path(".env")
            if env_file.exists():
                logger.info(f"配置文件: {env_file.absolute()}")
                # 使用python-dotenv加载.env文件
                env_values = dotenv_values(env_file)
                loaded_count = 0
                for key, value in env_values.items():
                    if key and value is not None and key not in os.environ:
                        os.environ[key] = str(value)
                        loaded_count += 1
                logger.info(f"已加载 {loaded_count} 个环境变量从 .env 文件")
            else:
                logger.info("未找到 .env 文件 - 使用系统环境变量")
        except ImportError:
            logger.warning("未安装 python-dotenv 库，使用手动解析")
            try:
                env_file = Path(".env")
                if env_file.exists():
                    logger.info(f"配置文件: {env_file.absolute()}")
                    loaded_count = 0
                    with open(env_file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip()
                                if key not in os.environ:
                                    os.environ[key] = value
                                    loaded_count += 1
                    logger.info(f"已加载 {loaded_count} 个环境变量从 .env 文件")
                else:
                    logger.info("未找到 .env 文件 - 使用系统环境变量")
            except Exception as e:
                logger.error(f"加载 .env 文件时出错: {e}")
        except Exception as e:
            logger.error(f"加载 .env 文件时出错: {e}")

    # 统计环境变量
    all_env_count = len(os.environ)
    plugin_env_count = len([k for k in os.environ.keys()
                           if any(prefix in k for prefix in ['HOST', 'PORT', 'SUPERUSERS', 'NOTIFY_', 'STATUS_CHECK_', 'INCLUDE_ROOM', 'COMMAND_'])])
    logger.info(f"环境变量统计: 总数 {all_env_count} 个, 插件相关 {plugin_env_count} 个")

    # 定义要检查的环境变量
    plugin_vars = {
        "基础配置": [
            "HOST", "PORT", "COMMAND_START", "COMMAND_SEP", "LOG_LEVEL"
        ],
        "用户和群组": [
            "SUPERUSERS", "NOTIFY_GROUPS"
        ],
        "动态监控": [
            "DYNAMIC_MONITOR_MAPPING",
            "DYNAMIC_MONITOR_INTERVAL",
            "DYNAMIC_ENABLE_SCREENSHOT",
            "BILIBILI_COOKIE"
        ],
        "直播监控": [
            "LIVE_MONITOR_MAPPING",
            "LIVE_MONITOR_INTERVAL",
            "LIVE_MONITOR_INCLUDE_INFO",
            "LIVE_MONITOR_USE_WEBSOCKET"
        ],
        "状态检查": [
            "STATUS_CHECK_ALLOWED_QQ",
            "STATUS_CHECK_SHOW_DETAILED",
            "STATUS_CHECK_SHOW_UPTIME",
            "STATUS_CHECK_SHOW_MEMORY"
        ]
    }

    # 记录所有插件相关环境变量
    for category, vars_list in plugin_vars.items():
        config_items = []
        for var in vars_list:
            value = os.getenv(var)
            if value is not None:
                # 对敏感信息进行部分隐藏
                if "SUPERUSERS" in var and value:
                    display_value = value[:10] + "..." if len(value) > 10 else value
                else:
                    display_value = value
                config_items.append(f"{var}={display_value}")
            else:
                config_items.append(f"{var}=(未设置)")

        # 将同一类别的配置项合并成一条日志
        if config_items:
            logger.info(f"{category}: {' | '.join(config_items)}")

    logger.info("环境配置加载完成")

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

# 调用环境变量记录函数（在NoneBot初始化之后）
log_environment_config()

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