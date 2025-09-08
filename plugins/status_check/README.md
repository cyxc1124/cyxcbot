# 机器人状态查询插件

## 功能描述

这个插件允许特定QQ号查询机器人的运行状态，包括运行时间、系统信息、内存使用情况等。

## 权限控制

- **智能权限检查**：只响应有权限的用户请求，无权限用户发送命令时机器人完全不会回复
- **超级用户优先**：优先使用系统 `SUPERUSERS` 配置中的QQ号
- **专用配置支持**：可通过环境变量 `STATUS_CHECK_ALLOWED_QQ` 单独配置允许的QQ号
- **默认权限**：如果没有配置任何专用QQ号，则只允许系统 `SUPERUSERS` 访问
- **安全日志**：所有权限检查操作都会记录日志，无权限的尝试仅记录警告日志而不会回复

## 命令使用

- `/status` - 查询机器人运行状态
- `/状态` - 查询机器人运行状态（别名）
- `/运行状态` - 查询机器人运行状态（别名）

## 状态信息

插件会显示以下信息：

### 基本信息
- 🤖 机器人运行状态
- ⏰ 运行时间（可配置是否显示）
- 🖥️ 系统信息
- 💾 内存使用情况（可配置是否显示）
- 🔗 机器人连接状态

### 详细信息（可配置是否显示）
- 📅 当前时间
- 🐍 Python版本
- 📦 NoneBot版本

## 配置选项

### 环境变量配置（推荐）

可以通过以下环境变量配置插件：

```bash
# 权限配置（优先使用SUPERUSERS）
SUPERUSERS='["120674547"]'                    # 系统超级用户（推荐）
STATUS_CHECK_ALLOWED_QQ='["120674547"]'      # 专用状态查询权限

# 显示选项配置
STATUS_CHECK_SHOW_DETAILED=true              # 显示详细状态信息
STATUS_CHECK_SHOW_UPTIME=true                # 显示运行时间
STATUS_CHECK_SHOW_MEMORY=true                # 显示内存使用情况
```

### 配置类定义

插件会自动从环境变量读取配置：

```python
class Config(BaseModel):
    # 允许查询状态的QQ号列表（优先使用SUPERUSERS）
    allowed_qq_numbers: List[int] = Field(default_factory=lambda: Config._get_allowed_qq_numbers())
    
    # 是否显示详细状态信息
    show_detailed_status: bool = Field(default_factory=lambda: Config._get_show_detailed_status())
    
    # 是否显示机器人运行时间
    show_uptime: bool = Field(default_factory=lambda: Config._get_show_uptime())
    
    # 是否显示内存使用情况
    show_memory_usage: bool = Field(default_factory=lambda: Config._get_show_memory_usage())
```

## 依赖

- `psutil` - 用于获取系统信息
- `platform` - 用于获取平台信息
- `nonebot2` - 机器人框架

## 安装

1. 确保已安装 `psutil`：
   ```bash
   pip install psutil
   ```

2. 插件会自动被NoneBot2加载

## 日志

插件会记录以下日志：
- 用户查询状态的操作
- 无权限用户尝试查询的警告
- 获取状态信息时的错误

## 安全说明

- **严格权限控制**：只有指定的QQ号才能触发状态查询，其他用户的命令会被完全忽略
- **无响应策略**：无权限用户发送命令时机器人不会有任何回复，避免暴露机器人存在
- **完整日志记录**：所有状态查询操作和无权限尝试都会记录日志，便于安全审计
- **信息安全**：插件只显示运行状态信息，不会暴露敏感的系统配置或密钥信息
- **双重检查**：同时支持超级用户权限和专用权限配置，提供灵活的访问控制 