---
sidebar_position: 1
---

# 环境变量

2.0 之后，**只有启动级配置**仍通过环境变量；业务配置（监控映射、B 站 Cookie、权限、模板等）全部在 Web Admin / 数据库中管理。

完整示例见仓库 [`env.example`](https://github.com/cyxc1124/cyxcbot/blob/main/env.example)。

## OneBot

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 机器人监听地址 |
| `PORT` | `8080` | 机器人监听端口 |
| `COMMAND_START` | `["/"]` | 命令起始字符 |
| `COMMAND_SEP` | `["."]` | 命令分隔字符 |
| `DRIVER` | `~fastapi+~httpx+~websockets` | NoneBot 驱动。官方 Bot 默认 Webhook，`httpx` 用于调用官方 API，`websockets` 兼容旧连接方式；`bot.py` 未设置时会补上 |

## Web Admin

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WEB_HOST` | `0.0.0.0` | API 监听地址 |
| `WEB_PORT` | `8081` | API 监听端口 |
| `WEB_SECRET_KEY` | — | JWT 签名与 Cookie 加密密钥。Web Admin **启动时必填**（≥32 字符，勿用占位值）；未设置时机器人仍可启动，但面板不监听 |
| `WEB_ADMIN_ENABLED` | `true` | 设为 `false` 可禁用 Web Admin（跳过密钥校验） |

生成示例：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Docker Compose 通过 `${WEB_SECRET_KEY:?...}` 注入，未设置时 **Compose 会直接失败**（与本地 `bot.py` 行为不同）。

## 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLALCHEMY_DATABASE_URL` | `sqlite+aiosqlite:///data/cyxcbot.db` | 数据库连接串 |

PostgreSQL 示例：

```bash
SQLALCHEMY_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/cyxcbot
```

数据库在 `bot.py` 启动时自动初始化（建表 / 应用迁移）。

## 日志

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | `INFO` | 终端 stdout 的初始最低级别；Web 保存值优先 |
| `LOG_FILE_ENABLED` | `true` | 设为 `false` 可禁用磁盘日志 |
| `LOG_FILE_PATH` | `data/logs/cyxcbot.log` | 磁盘日志路径模板 |
| `LOG_FILE_LEVEL` | 同 `LOG_LEVEL` | 写入文件的初始最低级别；Web 保存值优先 |
| `LOG_FILE_ROTATION` | `10 MB` | 单次运行内 active 文件切分大小 |
| `LOG_FILE_RETENTION` | `7 days` | 过期日志保留时长 |

终端和文件级别可在 Web `/logs` 分别保存，立即生效并持久化，无需重启；页面显示筛选保持独立。三条通道的级别、保留策略与文件名规则见 **[日志](./logging)**。

## TLS 信任库

`bot.py` 在创建客户端之前，将 aiohttp 的默认 TLS 信任库统一为随应用安装的 certifi Mozilla CA 包。Docker、Windows 包和源码启动均使用同一策略，保留证书链与主机名校验，避免重新信任宿主机中已被撤销信任的根证书。

aiohttp 默认连接不再加载操作系统、`SSL_CERT_FILE` 或 `SSL_CERT_DIR` 中的附加根证书。开发调用方如需连接私有 CA 服务或代理，应显式传入仅包含所需信任的 `SSLContext`，不要关闭 TLS 校验。HTTPX 和独立的 websockets 驱动仍遵循各自的信任配置；本策略不修改系统信任库。

## JWT 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_ALGORITHM` | `HS256` | JWT 算法 |
| `JWT_EXPIRE_MINUTES` | `1440` | Token 过期时间（分钟） |

## 业务配置不在环境变量中

监控映射、B 站 / 抖音 Cookie、**官方 QQ Bot AppID/Secret**、群策略、消息模板、**Rust 群管**（RCON 绑定、签到奖励、商城等）均存数据库，经 Web Admin 管理，无对应启动环境变量。

## 已弃用的业务环境变量

以下变量在 2.0 中已弃用，启动时会有提示，请改到 Web Admin 配置：

- `LIVE_MONITOR_*`
- `DYNAMIC_MONITOR_*`
- `STATUS_CHECK_*`
- `BILIBILI_COOKIE`（改到 Web Admin → B 站 → 账号）
- `SUPERUSERS`（改到 Web Admin → 系统 → 权限）
- `NOTIFY_GROUPS`（改到各监控页面的目标群/好友映射）

详见 [1.x 迁移指南](./migration-2.0)。
