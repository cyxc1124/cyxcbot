import platform
import time
from datetime import datetime

import psutil
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.exception import FinishedException
from nonebot.log import logger
from nonebot.permission import SUPERUSER

from shared.config.command_aliases import match_plain
from shared.config.service import get_config_service
from shared.monitor.system_metrics import (
    detect_container_environment,
    get_cached_snapshot,
    get_container_cpu_limit,
    get_container_memory_info,
)
from shared.status_check_policy import (
    is_status_check_enabled_for_group_from_snapshot,
    is_status_check_enabled_for_user_from_snapshot,
)

# 记录机器人启动时间
start_time = time.time()


# 权限检查函数
def _get_allowed_qq_numbers() -> set[int]:
    """从 Web Admin 数据库读取允许查询状态的 QQ 列表"""
    try:
        from shared.config.service import get_config_service

        allowed: set[int] = set()
        for qq in get_config_service().get_snapshot().status_check_allowed_qq:
            qq_str = str(qq).strip()
            if qq_str.isdigit():
                allowed.add(int(qq_str))
        return allowed
    except Exception:
        logger.opt(exception=True).warning("读取状态查询权限配置失败")
        return set()


async def check_status_permission(
    bot: Bot, event: GroupMessageEvent | PrivateMessageEvent
) -> bool:
    """检查用户是否有查询状态的权限"""
    user_id = event.user_id

    if await SUPERUSER(bot, event):
        logger.info("NoneBot 超级用户 {} 查询机器人状态", user_id)
        return True

    if user_id in _get_allowed_qq_numbers():
        logger.info("允许的用户 {} 查询机器人状态", user_id)
        return True

    snap = get_config_service().get_snapshot()
    if isinstance(event, GroupMessageEvent):
        if is_status_check_enabled_for_group_from_snapshot(str(event.group_id), snap):
            logger.info("群组 {} 内用户 {} 查询机器人状态", event.group_id, user_id)
            return True
    elif isinstance(event, PrivateMessageEvent):
        if is_status_check_enabled_for_user_from_snapshot(str(user_id), snap):
            logger.info("好友 {} 查询机器人状态", user_id)
            return True

    logger.warning("用户 {} 尝试查询机器人状态，但无权限", user_id)
    return False


# 创建状态查询命令处理器（触发词可在 Web Admin 设置 → 命令 中自定义）
status_cmd = on_message(priority=5, block=False)


@status_cmd.handle()
async def handle_status_command(
    bot: Bot, event: GroupMessageEvent | PrivateMessageEvent
):
    """处理状态查询命令"""
    text = event.get_plaintext().strip()
    config = get_config_service().get_snapshot()
    # is_tome 对私聊消息恒为 True（好友消息天然"发给"机器人），若直接传入会让
    # match_plain 走 @机器人 模糊匹配分支——好友随口一句"状态怎么样"/"请看运行
    # 状态"就会命中。仅群聊里"被 @/回复"才算模糊匹配场景；私聊强制精确匹配，
    # 保持迁移前 on_command 的语义（需完整输入触发词，而非包含即命中）。
    is_tome = isinstance(event, GroupMessageEvent) and event.is_tome()
    if not match_plain(text, "status", config.command_aliases, is_tome=is_tome):
        return

    # 检查权限
    if not await check_status_permission(bot, event):
        # 无权限时静默退出，不回复任何消息
        return

    try:
        # 构建状态信息
        status_info = await get_bot_status()
        await status_cmd.finish(status_info)

    except FinishedException:
        # FinishedException是NoneBot内部异常，用于结束处理器，不应该处理
        raise
    except Exception:
        logger.opt(exception=True).error("获取机器人状态失败")
        await status_cmd.finish("❌ 获取状态信息失败，请稍后重试")


async def get_bot_status() -> str:
    """获取机器人运行状态信息"""
    try:
        from .config import Config

        config = Config.from_service()
        # 计算运行时间
        uptime_seconds = int(time.time() - start_time)
        uptime_str = format_uptime(uptime_seconds)

        # 获取系统信息
        system_info = get_system_info()

        # 构建状态消息
        status_msg = "机器草 运行状态\n"
        status_msg += "=" * 35 + "\n"
        status_msg += f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        # 基础运行信息
        if config.show_uptime:
            status_msg += f"运行时长: {uptime_str}\n"

        status_msg += f"操作系统: {system_info}\n"

        # 进程 CPU（读后台采样缓存，不阻塞事件循环）
        status_msg += f"CPU: {get_process_cpu_info()}\n"

        if config.show_memory_usage:
            try:
                import psutil

                process = psutil.Process()
                process_memory = process.memory_info().rss / (1024**2)
                status_msg += f"内存: {process_memory:.1f}MB\n"
            except Exception as e:
                logger.debug("获取进程内存失败: {}", e)
                status_msg += "内存: 无法获取\n"

        if config.show_detailed_status:
            status_msg += "\n" + "详细技术信息" + "\n"
            status_msg += "-" * 20 + "\n"
            status_msg += f"Python版本: {platform.python_version()}\n"
            status_msg += f"NoneBot版本: {get_nonebot_version()}\n"

            # 添加更多技术信息
            tech_info = get_technical_info()
            status_msg += tech_info

        return status_msg

    except Exception:
        logger.opt(exception=True).error("构建状态信息失败")
        return "❌ 获取状态信息时发生错误"


def format_uptime(seconds: int) -> str:
    """格式化运行时间"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    if days > 0:
        return f"{days}天{hours}小时{minutes}分钟"
    elif hours > 0:
        return f"{hours}小时{minutes}分钟"
    elif minutes > 0:
        return f"{minutes}分钟{seconds}秒"
    else:
        return f"{seconds}秒"


def get_system_info() -> str:
    """获取系统信息（容器感知）"""
    try:
        system = platform.system()
        release = platform.release()
        machine = platform.machine()

        # 检测容器环境
        env = detect_container_environment()

        base_info = f"{system} {release} ({machine})"

        if env["is_container"]:
            if env["is_kubernetes"]:
                return f"{base_info} [Kubernetes Pod]"
            elif env["is_docker"]:
                return f"{base_info} [Docker Container]"
            else:
                return f"{base_info} [Container]"

        return base_info
    except Exception:
        logger.opt(exception=True).error("获取系统信息失败")
        return "未知"


def get_memory_info() -> str:
    """获取内存使用情况"""
    try:
        memory = psutil.virtual_memory()
        used_mb = memory.used // (1024 * 1024)
        total_mb = memory.total // (1024 * 1024)
        percent = memory.percent
        return f"{used_mb}MB / {total_mb}MB ({percent:.1f}%)"
    except Exception:
        logger.opt(exception=True).error("获取内存信息失败")
        return "未知"


def get_bot_connection_status() -> str:
    """获取机器人连接状态"""
    try:
        from nonebot import get_driver

        driver = get_driver()
        bots = driver.bots

        if bots:
            bot_count = len(bots)
            return f"已连接 {bot_count} 个机器人"
        else:
            return "未连接任何机器人"
    except Exception:
        logger.opt(exception=True).error("获取机器人连接状态失败")
        return "未知"


def get_detailed_memory_info() -> str:
    """获取详细内存使用情况（优先显示容器信息）"""
    try:
        env = detect_container_environment()

        # 如果在容器中，尝试获取容器内存信息
        if env["is_container"]:
            container_memory = get_container_memory_info()
            if container_memory:
                return f"{container_memory['used_gb']:.1f}GB/{container_memory['total_gb']:.1f}GB (使用率{container_memory['percent']:.1f}%, 可用{container_memory['available_gb']:.1f}GB) [容器]"
            else:
                # 容器内存信息获取失败，记录可能的原因
                logger.info(
                    "未检测到容器内存限制，可能原因：Pod未配置resources.limits.memory"
                )

        # 使用系统内存信息
        memory = psutil.virtual_memory()
        used_gb = memory.used / (1024**3)
        total_gb = memory.total / (1024**3)
        available_gb = memory.available / (1024**3)
        percent = memory.percent

        if env["is_container"]:
            suffix = " [宿主机，Pod未设置内存限制]"
        else:
            suffix = ""

        return f"{used_gb:.1f}GB/{total_gb:.1f}GB (使用率{percent:.1f}%, 可用{available_gb:.1f}GB){suffix}"
    except Exception:
        logger.opt(exception=True).error("获取详细内存信息失败")
        return get_memory_info()  # 降级到基础信息


def get_cpu_info() -> str:
    """获取CPU使用率和核心数（容器感知，读后台采样缓存）"""
    try:
        snap = get_cached_snapshot()
        cpu_percent = snap.cpu_percent if snap is not None else psutil.cpu_percent()
        cpu_count = snap.cpu_count if snap is not None else (psutil.cpu_count() or 1)

        env = detect_container_environment()
        cpu_freq = psutil.cpu_freq()

        if env["is_container"]:
            cpu_limit = get_container_cpu_limit()

            if cpu_limit:
                freq_info = f", {cpu_freq.current:.0f}MHz" if cpu_freq else ""
                return f"{cpu_percent:.1f}% (限制{cpu_limit:.1f}核{freq_info}, 宿主机{cpu_count}核) [容器]"
            else:
                freq_info = f", {cpu_freq.current:.0f}MHz" if cpu_freq else ""
                return f"{cpu_percent:.1f}% ({cpu_count}核{freq_info}) [宿主机，Pod未设置CPU限制]"
        else:
            if cpu_freq:
                return f"{cpu_percent:.1f}% ({cpu_count}核, {cpu_freq.current:.0f}MHz)"
            else:
                return f"{cpu_percent:.1f}% ({cpu_count}核)"
    except Exception:
        logger.opt(exception=True).error("获取CPU信息失败")
        return "无法获取"


def get_process_cpu_info() -> str:
    """获取本进程 CPU 使用率（读后台采样缓存）"""
    try:
        snap = get_cached_snapshot()
        if snap is not None:
            return f"{snap.process_cpu_percent:.1f}%"
        return f"{psutil.Process().cpu_percent():.1f}%"
    except Exception:
        logger.opt(exception=True).error("获取进程CPU信息失败")
        return "无法获取"


def get_detailed_connection_status() -> str:
    """获取详细连接状态"""
    try:
        from nonebot import get_driver

        driver = get_driver()
        bots = driver.bots

        if not bots:
            return "未连接"

        status_details = []
        for bot_id, bot in bots.items():
            bot_type = type(bot).__name__
            status_details.append(f"{bot_id}({bot_type})")

        return f"{len(bots)}个连接: {', '.join(status_details)}"
    except Exception:
        logger.opt(exception=True).error("获取详细连接状态失败")
        return get_bot_connection_status()


def get_plugin_status() -> str:
    """获取插件加载状态"""
    try:
        from nonebot import get_loaded_plugins

        plugins = get_loaded_plugins()
        plugin_names = []

        for plugin in plugins:
            # 获取插件名称，优先使用模块名
            name = getattr(plugin, "name", plugin.module_name.split(".")[-1])
            plugin_names.append(name)

        return f"{len(plugins)}个插件已加载: {', '.join(plugin_names[:3])}{'...' if len(plugin_names) > 3 else ''}"
    except Exception:
        logger.opt(exception=True).error("获取插件状态失败")
        return "无法获取插件状态"


def get_technical_info() -> str:
    """获取技术详细信息（容器优化）"""
    try:
        tech_info = ""
        env = detect_container_environment()

        # 网络连接数（仅在非容器环境或连接数异常时显示）
        try:
            connections = len(psutil.net_connections())
            # 在容器中，只有当连接数异常时才显示（通常容器内连接很少）
            if not env["is_container"] or connections > 10:
                suffix = " [容器内可见]" if env["is_container"] else ""
                tech_info += f"网络连接数: {connections}{suffix}\n"
        except psutil.Error, OSError:
            pass

        # 系统启动时间
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            if env["is_container"]:
                tech_info += (
                    f"容器宿主机启动: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
            else:
                tech_info += f"系统启动: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        except psutil.Error, OSError, OverflowError, ValueError:
            pass

        return tech_info
    except Exception:
        logger.opt(exception=True).error("获取技术信息失败")
        return ""


def get_nonebot_version() -> str:
    """获取NoneBot版本"""
    try:
        import nonebot

        return nonebot.__version__
    except Exception:
        logger.opt(exception=True).error("获取NoneBot版本失败")
        return "未知"
