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
from .config import Config

# 获取插件配置
config = get_plugin_config(Config)

# 记录机器人启动时间
start_time = time.time()

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
    user_id = event.user_id
    
    # 检查用户是否有权限查询状态
    if user_id not in config.allowed_qq_numbers:
        logger.warning(f"用户 {user_id} 尝试查询机器人状态，但无权限")
        await status_cmd.finish("❌ 您没有权限查询机器人状态")
        return
    
    logger.info(f"用户 {user_id} 查询机器人状态")
    
    try:
        # 构建状态信息
        status_info = await get_bot_status()
        await status_cmd.finish(status_info)
        
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
        status_msg = "🤖 机器人运行状态\n"
        status_msg += "=" * 20 + "\n"
        
        if config.show_uptime:
            status_msg += f"⏰ 运行时间: {uptime_str}\n"
        
        status_msg += f"🖥️ 系统: {system_info}\n"
        
        if config.show_memory_usage:
            status_msg += f"💾 内存使用: {memory_info}\n"
        
        status_msg += f"🔗 连接状态: {bot_status}\n"
        
        if config.show_detailed_status:
            status_msg += "=" * 20 + "\n"
            status_msg += f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_msg += f"🐍 Python版本: {platform.python_version()}\n"
            status_msg += f"📦 NoneBot版本: {get_nonebot_version()}\n"
        
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
            return f"✅ 已连接 {bot_count} 个机器人"
        else:
            return "❌ 未连接任何机器人"
    except Exception as e:
        logger.error(f"获取机器人连接状态失败: {e}")
        return "未知"

def get_nonebot_version() -> str:
    """获取NoneBot版本"""
    try:
        import nonebot
        return nonebot.__version__
    except Exception as e:
        logger.error(f"获取NoneBot版本失败: {e}")
        return "未知" 