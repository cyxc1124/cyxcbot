import nonebot
import os
import logging
from nonebot.log import logger, LoguruHandler
from nonebot.adapters.console import Adapter as ConsoleAdapter  # 避免重复命名
from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter  # 添加OneBot适配器

# 记录环境变量配置（用于调试）
def log_environment_config():
    """记录当前环境变量配置到日志"""
    logger.info("🔧 Environment Variables Debug Info")
    
    # 检测运行环境
    is_kubernetes = any(key.startswith(('KUBERNETES_', 'KUBE_')) for key in os.environ)
    is_docker = os.getenv('DOCKER_CONTAINER', '').lower() == 'true' or os.path.exists('/.dockerenv')
    
    if is_kubernetes:
        logger.info("🎯 Environment: Kubernetes")
        logger.info("📄 Using ConfigMap/Environment Variables (K8s)")
    elif is_docker:
        logger.info("🐳 Environment: Docker Container")  
        logger.info("📄 Using Docker Environment Variables")
    else:
        logger.info("🖥️ Environment: Local Development")
        
        # 在本地环境中尝试加载.env文件
        try:
            from pathlib import Path
            env_file = Path(".env")
            if env_file.exists():
                logger.info(f"📄 Loading .env file: {env_file.absolute()}")
                loaded_count = 0
                # 手动读取.env文件
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            # 设置到环境变量中（如果还没有设置的话）
                            if key not in os.environ:
                                os.environ[key] = value
                                loaded_count += 1
                logger.info(f"📥 Loaded {loaded_count} variables from .env file")
            else:
                logger.info("📄 No .env file found - using system environment variables")
        except Exception as e:
            logger.error(f"⚠️ Error loading .env file: {e}")
    
    # 统计环境变量
    all_env_count = len(os.environ)
    plugin_env_count = len([k for k in os.environ.keys() 
                           if any(prefix in k for prefix in ['HOST', 'PORT', 'SUPERUSERS', 'NOTIFY_', 'STATUS_CHECK_', 'INCLUDE_ROOM', 'COMMAND_'])])
    logger.info(f"📊 Total environment variables: {all_env_count}, Plugin-related: {plugin_env_count}")
    
    # 定义要检查的环境变量
    plugin_vars = {
        "Basic Config": [
            "HOST", "PORT", "COMMAND_START", "COMMAND_SEP"
        ],
        "User & Groups": [
            "SUPERUSERS", "NOTIFY_GROUPS"
        ],
        "Stream Notify": [
            "INCLUDE_ROOM_INFO"
        ],
        "Status Check": [
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
                config_items.append(f"{var}=(not set)")
        
        # 将同一类别的配置项合并成一条日志
        if config_items:
            logger.info(f"📂 {category}: {' | '.join(config_items)}")
    
    logger.info("🔧 Environment configuration loaded")

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

# 初始化 NoneBot
nonebot.init()

# 配置日志级别
configure_logging()

# 调用环境变量记录函数（在NoneBot初始化之后）
log_environment_config()

# 配置控制台适配器为无头模式
nonebot.get_driver().config.console_headless_mode = True

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(ConsoleAdapter)
driver.register_adapter(OneBotAdapter)  # 注册OneBot适配器

# 在这里加载插件
nonebot.load_builtin_plugins("echo")  # 内置插件
nonebot.load_plugins("plugins")  # 加载本地插件
# nonebot.load_plugin("thirdparty_plugin")  # 第三方插件

if __name__ == "__main__":
    nonebot.run()