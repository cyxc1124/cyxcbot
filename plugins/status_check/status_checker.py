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
    except Exception as exc:
        logger.debug(f"读取状态查询权限配置失败: {exc}")
        return set()


async def check_status_permission(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent) -> bool:
    """检查用户是否有查询状态的权限"""
    user_id = event.user_id

    if await SUPERUSER(bot, event):
        logger.info(f"NoneBot 超级用户 {user_id} 查询机器人状态")
        return True

    if user_id in _get_allowed_qq_numbers():
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
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        from shared.config.service import get_config_service
        from shared.group_policy import is_group_message_enabled_from_snapshot

        if not is_group_message_enabled_from_snapshot(group_id, get_config_service().get_snapshot()):
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
        status_msg = "机器草 运行状态\n"
        status_msg += "=" * 35 + "\n"
        status_msg += f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
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
        
        # 获取进程内存信息
        try:
            import psutil
            process = psutil.Process()
            process_memory = process.memory_info().rss / (1024 ** 2)
            status_msg += f"进程内存: {process_memory:.1f}MB\n"
        except Exception as e:
            logger.debug(f"获取进程内存失败: {e}")
            status_msg += f"进程内存: 无法获取\n"
        
        if config.show_detailed_status:
            status_msg += "\n" + "详细技术信息" + "\n"
            status_msg += "-" * 20 + "\n"
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
    """获取系统信息（容器感知）"""
    try:
        system = platform.system()
        release = platform.release()
        machine = platform.machine()
        
        # 检测容器环境
        env = detect_container_environment()
        
        base_info = f"{system} {release} ({machine})"
        
        if env['is_container']:
            if env['is_kubernetes']:
                return f"{base_info} [Kubernetes Pod]"
            elif env['is_docker']:
                return f"{base_info} [Docker Container]"
            else:
                return f"{base_info} [Container]"
        
        return base_info
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

def detect_container_environment():
    """检测容器环境"""
    import os
    
    # 检查是否在Docker容器中
    is_docker = (
        os.path.exists('/.dockerenv') or
        os.getenv('DOCKER_CONTAINER', '').lower() == 'true'
    )
    
    # 检查是否在Kubernetes中
    is_kubernetes = any(key.startswith(('KUBERNETES_', 'KUBE_')) for key in os.environ)
    
    # 检查cgroup信息
    try:
        if os.path.exists('/proc/1/cgroup'):
            with open('/proc/1/cgroup', 'r') as f:
                cgroup_info = f.read()
                if 'docker' in cgroup_info or 'kubepods' in cgroup_info:
                    is_docker = True
    except:
        pass
    
    return {
        'is_container': is_docker or is_kubernetes,
        'is_docker': is_docker,
        'is_kubernetes': is_kubernetes,
        'container_type': 'Kubernetes Pod' if is_kubernetes else ('Docker Container' if is_docker else 'Physical/VM')
    }

def get_container_memory_info():
    """获取容器内存信息（cgroup限制）- 增强版"""
    import os
    import glob
    
    debug_info = []
    
    try:
        # 扩展的cgroup路径列表，覆盖更多可能的位置
        memory_limit_paths = [
            # cgroup v1 标准路径
            '/sys/fs/cgroup/memory/memory.limit_in_bytes',
            # cgroup v2 标准路径
            '/sys/fs/cgroup/memory.max',
            # Kubernetes特定路径
            '/sys/fs/cgroup/memory/kubepods*/memory.limit_in_bytes',
            '/sys/fs/cgroup/memory/kubepods.slice/*/memory.limit_in_bytes',
            # Docker特定路径
            '/sys/fs/cgroup/memory/docker/*/memory.limit_in_bytes',
            # systemd路径
            '/sys/fs/cgroup/memory/system.slice/*/memory.limit_in_bytes'
        ]
        
        memory_usage_paths = [
            # cgroup v1 标准路径
            '/sys/fs/cgroup/memory/memory.usage_in_bytes',
            # cgroup v2 标准路径
            '/sys/fs/cgroup/memory.current',
            # Kubernetes特定路径
            '/sys/fs/cgroup/memory/kubepods*/memory.usage_in_bytes',
            '/sys/fs/cgroup/memory/kubepods.slice/*/memory.usage_in_bytes',
            # Docker特定路径
            '/sys/fs/cgroup/memory/docker/*/memory.usage_in_bytes',
            # systemd路径
            '/sys/fs/cgroup/memory/system.slice/*/memory.usage_in_bytes'
        ]
        
        limit_bytes = None
        usage_bytes = None
        found_limit_file = None
        found_usage_file = None
        
        # 查找内存限制文件
        for pattern in memory_limit_paths:
            if '*' in pattern:
                # 使用glob匹配通配符路径
                matched_files = glob.glob(pattern)
                for limit_file in matched_files:
                    if os.path.exists(limit_file):
                        try:
                            with open(limit_file, 'r') as f:
                                content = f.read().strip()
                                debug_info.append(f"检查限制文件 {limit_file}: {content}")
                                if content != 'max' and content.isdigit():
                                    limit_bytes = int(content)
                                    found_limit_file = limit_file
                                    break
                        except Exception as e:
                            debug_info.append(f"读取失败 {limit_file}: {e}")
                if limit_bytes:
                    break
            else:
                if os.path.exists(pattern):
                    try:
                        with open(pattern, 'r') as f:
                            content = f.read().strip()
                            debug_info.append(f"检查限制文件 {pattern}: {content}")
                            if content != 'max' and content.isdigit():
                                limit_bytes = int(content)
                                found_limit_file = pattern
                                break
                    except Exception as e:
                        debug_info.append(f"读取失败 {pattern}: {e}")
        
        # 查找内存使用文件
        for pattern in memory_usage_paths:
            if '*' in pattern:
                # 使用glob匹配通配符路径
                matched_files = glob.glob(pattern)
                for usage_file in matched_files:
                    if os.path.exists(usage_file):
                        try:
                            with open(usage_file, 'r') as f:
                                content = f.read().strip()
                                if content.isdigit():
                                    usage_bytes = int(content)
                                    found_usage_file = usage_file
                                    debug_info.append(f"找到使用文件 {usage_file}: {content}")
                                    break
                        except Exception as e:
                            debug_info.append(f"读取失败 {usage_file}: {e}")
                if usage_bytes is not None:
                    break
            else:
                if os.path.exists(pattern):
                    try:
                        with open(pattern, 'r') as f:
                            content = f.read().strip()
                            if content.isdigit():
                                usage_bytes = int(content)
                                found_usage_file = pattern
                                debug_info.append(f"找到使用文件 {pattern}: {content}")
                                break
                    except Exception as e:
                        debug_info.append(f"读取失败 {pattern}: {e}")
        
        # 记录调试信息
        logger.debug(f"容器内存检测调试: {'; '.join(debug_info)}")
        
        if limit_bytes and usage_bytes is not None:
            # 处理无限制的情况（通常是一个很大的数字）
            if limit_bytes > 1024**4:  # 大于1TB，可能是无限制
                logger.debug(f"检测到无限制内存设置: {limit_bytes} bytes")
                return None
                
            limit_gb = limit_bytes / (1024 ** 3)
            usage_gb = usage_bytes / (1024 ** 3)
            available_gb = limit_gb - usage_gb
            usage_percent = (usage_gb / limit_gb) * 100
            
            logger.info(f"成功读取容器内存: 限制={limit_gb:.1f}GB, 使用={usage_gb:.1f}GB (来源: {found_limit_file})")
            
            return {
                'used_gb': usage_gb,
                'total_gb': limit_gb,
                'available_gb': available_gb,
                'percent': usage_percent,
                'is_container': True,
                'limit_file': found_limit_file,
                'usage_file': found_usage_file
            }
        else:
            logger.debug(f"未找到有效的容器内存信息: limit_bytes={limit_bytes}, usage_bytes={usage_bytes}")
            
    except Exception as e:
        logger.debug(f"容器内存检测异常: {e}")
    
    return None

def get_detailed_memory_info() -> str:
    """获取详细内存使用情况（优先显示容器信息）"""
    try:
        env = detect_container_environment()
        
        # 如果在容器中，尝试获取容器内存信息
        if env['is_container']:
            container_memory = get_container_memory_info()
            if container_memory:
                return f"{container_memory['used_gb']:.1f}GB/{container_memory['total_gb']:.1f}GB (使用率{container_memory['percent']:.1f}%, 可用{container_memory['available_gb']:.1f}GB) [容器]"
            else:
                # 容器内存信息获取失败，记录可能的原因
                logger.info("未检测到容器内存限制，可能原因：Pod未配置resources.limits.memory")
        
        # 使用系统内存信息
        memory = psutil.virtual_memory()
        used_gb = memory.used / (1024 ** 3)
        total_gb = memory.total / (1024 ** 3)
        available_gb = memory.available / (1024 ** 3)
        percent = memory.percent
        
        if env['is_container']:
            suffix = " [宿主机，Pod未设置内存限制]"
        else:
            suffix = ""
        
        return f"{used_gb:.1f}GB/{total_gb:.1f}GB (使用率{percent:.1f}%, 可用{available_gb:.1f}GB){suffix}"
    except Exception as e:
        logger.error(f"获取详细内存信息失败: {e}")
        return get_memory_info()  # 降级到基础信息

def get_container_cpu_limit():
    """获取容器CPU限制信息"""
    import os
    try:
        # CPU配额文件路径
        cpu_quota_paths = [
            '/sys/fs/cgroup/cpu/cpu.cfs_quota_us',
            '/sys/fs/cgroup/cpu.max',  # cgroup v2
        ]
        cpu_period_paths = [
            '/sys/fs/cgroup/cpu/cpu.cfs_period_us',
            '/sys/fs/cgroup/cpu.max',  # cgroup v2 (same file, different format)
        ]
        
        quota = None
        period = None
        
        # 查找CPU配额
        for quota_file in cpu_quota_paths:
            if os.path.exists(quota_file):
                try:
                    with open(quota_file, 'r') as f:
                        content = f.read().strip()
                        if quota_file.endswith('cpu.max'):  # cgroup v2
                            parts = content.split()
                            if len(parts) >= 2 and parts[0] != 'max':
                                quota = int(parts[0])
                                period = int(parts[1])
                                break
                        else:  # cgroup v1
                            if content != '-1' and content.isdigit():
                                quota = int(content)
                except:
                    continue
        
        # 查找CPU周期（仅cgroup v1需要）
        if quota and not period:
            for period_file in cpu_period_paths:
                if os.path.exists(period_file):
                    try:
                        with open(period_file, 'r') as f:
                            content = f.read().strip()
                            if content.isdigit():
                                period = int(content)
                                break
                    except:
                        continue
        
        if quota and period and quota > 0:
            # 计算CPU限制（以核心数表示）
            cpu_limit_cores = quota / period
            return cpu_limit_cores
            
    except Exception as e:
        logger.debug(f"读取容器CPU限制失败: {e}")
    
    return None

def get_cpu_info() -> str:
    """获取CPU使用率和核心数（容器感知）"""
    try:
        env = detect_container_environment()
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        if env['is_container']:
            # 尝试获取容器CPU限制
            cpu_limit = get_container_cpu_limit()
            
            if cpu_limit:
                # 显示容器CPU限制
                freq_info = f", {cpu_freq.current:.0f}MHz" if cpu_freq else ""
                return f"{cpu_percent:.1f}% (限制{cpu_limit:.1f}核{freq_info}, 宿主机{cpu_count}核) [容器]"
            else:
                # 未设置CPU限制，显示宿主机信息
                freq_info = f", {cpu_freq.current:.0f}MHz" if cpu_freq else ""
                return f"{cpu_percent:.1f}% ({cpu_count}核{freq_info}) [宿主机，Pod未设置CPU限制]"
        else:
            # 物理机环境
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
    """获取技术详细信息（容器优化）"""
    try:
        tech_info = ""
        env = detect_container_environment()
        
        # 网络连接数（仅在非容器环境或连接数异常时显示）
        try:
            connections = len(psutil.net_connections())
            # 在容器中，只有当连接数异常时才显示（通常容器内连接很少）
            if not env['is_container'] or connections > 10:
                suffix = " [容器内可见]" if env['is_container'] else ""
                tech_info += f"网络连接数: {connections}{suffix}\n"
        except:
            pass
        
        # 系统启动时间
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            if env['is_container']:
                tech_info += f"容器宿主机启动: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
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