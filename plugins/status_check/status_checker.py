import time
import psutil
import platform
from datetime import datetime
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.log import logger
from nonebot import get_plugin_config
from nonebot.exception import FinishedException
from .config import Config

# 获取插件配置
config = get_plugin_config(Config)

# 记录机器人启动时间
start_time = time.time()

# 权限检查函数
async def check_status_permission(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent) -> bool:
    """检查用户是否有查询状态的权限"""
    user_id = event.user_id
    
    # 优先检查是否为超级用户
    if await SUPERUSER(bot, event):
        logger.info(f"超级用户 {user_id} 查询机器人状态")
        return True
    
    # 检查是否在允许的QQ号列表中
    if user_id in config.allowed_qq_numbers:
        logger.info(f"允许的用户 {user_id} 查询机器人状态")
        return True
    
    # 无权限时记录警告并拒绝
    logger.warning(f"用户 {user_id} 尝试查询机器人状态，但无权限")
    return False

# 创建状态查询命令处理器
status_cmd = on_command(
    "status",
    aliases={"状态", "运行状态"},
    priority=5,
    block=True
)

@status_cmd.handle()
async def handle_status_command(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    """处理状态查询命令"""
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
    except Exception as e:
        logger.error(f"获取机器人状态失败: {e}")
        await status_cmd.finish("❌ 获取状态信息失败，请稍后重试")

async def get_bot_status() -> str:
    """获取机器人运行状态信息"""
    try:
        # 计算运行时间
        uptime_seconds = int(time.time() - start_time)
        uptime_str = format_uptime(uptime_seconds)
        
        # 获取系统信息
        system_info = get_system_info()
        
        # 获取内存使用情况
        memory_info = get_memory_info()
        
        # 获取机器人连接状态
        bot_status = get_bot_connection_status()
        
        # 构建状态消息
        status_msg = "CyxcBot 运行状态报告\n"
        status_msg += "=" * 35 + "\n"
        
        # 基础运行信息
        if config.show_uptime:
            status_msg += f"运行时长: {uptime_str}\n"
        
        status_msg += f"操作系统: {system_info}\n"
        
        if config.show_memory_usage:
            # 获取更详细的内存信息
            memory_detail = get_detailed_memory_info()
            status_msg += f"内存使用: {memory_detail}\n"
        
        # 获取CPU使用率
        cpu_info = get_cpu_info()
        status_msg += f"CPU使用率: {cpu_info}\n"
        
        # 连接状态
        connection_detail = get_detailed_connection_status()
        status_msg += f"连接状态: {connection_detail}\n"
        
        # 插件状态
        plugin_status = get_plugin_status()
        status_msg += f"插件状态: {plugin_status}\n"
        
        if config.show_detailed_status:
            status_msg += "\n" + "详细技术信息" + "\n"
            status_msg += "-" * 20 + "\n"
            status_msg += f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_msg += f"Python版本: {platform.python_version()}\n"
            status_msg += f"NoneBot版本: {get_nonebot_version()}\n"
            
            # 添加更多技术信息
            tech_info = get_technical_info()
            status_msg += tech_info
        
        return status_msg
        
    except Exception as e:
        logger.error(f"构建状态信息失败: {e}")
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
    """获取系统信息"""
    try:
        system = platform.system()
        release = platform.release()
        machine = platform.machine()
        return f"{system} {release} ({machine})"
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return "未知"

def get_memory_info() -> str:
    """获取内存使用情况"""
    try:
        memory = psutil.virtual_memory()
        used_mb = memory.used // (1024 * 1024)
        total_mb = memory.total // (1024 * 1024)
        percent = memory.percent
        return f"{used_mb}MB / {total_mb}MB ({percent:.1f}%)"
    except Exception as e:
        logger.error(f"获取内存信息失败: {e}")
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
    except Exception as e:
        logger.error(f"获取机器人连接状态失败: {e}")
        return "未知"

def get_detailed_memory_info() -> str:
    """获取详细内存使用情况"""
    try:
        memory = psutil.virtual_memory()
        used_gb = memory.used / (1024 ** 3)
        total_gb = memory.total / (1024 ** 3)
        available_gb = memory.available / (1024 ** 3)
        percent = memory.percent
        return f"{used_gb:.1f}GB/{total_gb:.1f}GB (使用率{percent:.1f}%, 可用{available_gb:.1f}GB)"
    except Exception as e:
        logger.error(f"获取详细内存信息失败: {e}")
        return get_memory_info()  # 降级到基础信息

def get_cpu_info() -> str:
    """获取CPU使用率和核心数"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            return f"{cpu_percent:.1f}% ({cpu_count}核, {cpu_freq.current:.0f}MHz)"
        else:
            return f"{cpu_percent:.1f}% ({cpu_count}核)"
    except Exception as e:
        logger.error(f"获取CPU信息失败: {e}")
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
    except Exception as e:
        logger.error(f"获取详细连接状态失败: {e}")
        return get_bot_connection_status()

def get_plugin_status() -> str:
    """获取插件加载状态"""
    try:
        from nonebot import get_loaded_plugins
        plugins = get_loaded_plugins()
        plugin_names = []
        
        for plugin in plugins:
            # 获取插件名称，优先使用模块名
            name = getattr(plugin, 'name', plugin.module_name.split('.')[-1])
            plugin_names.append(name)
        
        return f"{len(plugins)}个插件已加载: {', '.join(plugin_names[:3])}{'...' if len(plugin_names) > 3 else ''}"
    except Exception as e:
        logger.error(f"获取插件状态失败: {e}")
        return "无法获取插件状态"

def get_technical_info() -> str:
    """获取技术详细信息"""
    try:
        tech_info = ""
        
        # 磁盘使用情况
        try:
            import os
            # 根据操作系统选择磁盘路径
            disk_path = '/' if os.name != 'nt' else 'C:\\'
            disk = psutil.disk_usage(disk_path)
            disk_used_gb = disk.used / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
            disk_percent = (disk.used / disk.total) * 100
            tech_info += f"磁盘使用: {disk_used_gb:.1f}GB/{disk_total_gb:.1f}GB ({disk_percent:.1f}%)\n"
        except:
            pass
        
        # 网络连接数
        try:
            connections = len(psutil.net_connections())
            tech_info += f"网络连接数: {connections}\n"
        except:
            pass
        
        # 进程信息
        try:
            process = psutil.Process()
            process_memory = process.memory_info().rss / (1024 ** 2)
            tech_info += f"进程内存: {process_memory:.1f}MB\n"
            tech_info += f"进程PID: {process.pid}\n"
        except:
            pass
        
        # 系统启动时间
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            tech_info += f"系统启动: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        except:
            pass
            
        return tech_info
    except Exception as e:
        logger.error(f"获取技术信息失败: {e}")
        return ""

def get_nonebot_version() -> str:
    """获取NoneBot版本"""
    try:
        import nonebot
        return nonebot.__version__
    except Exception as e:
        logger.error(f"获取NoneBot版本失败: {e}")
        return "未知" 