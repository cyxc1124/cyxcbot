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

## Web Admin

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WEB_HOST` | `0.0.0.0` | API 监听地址 |
| `WEB_PORT` | `8081` | API 监听端口 |
| `WEB_SECRET_KEY` | — | JWT 签名密钥（**必填**） |
| `WEB_ADMIN_ENABLED` | `true` | 设为 `false` 可禁用 Web Admin |

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
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`；由 NoneBot 在启动时读取，**仅控制终端 stdout 的过滤级别** |

Web Admin 的 `/logs` 页面 intentionally 比终端更 verbose：广播 sink 固定为 `DEBUG`，因此 `LOG_LEVEL=INFO` 或 `WARNING` 时终端不显示 DEBUG，但 Web 日志页仍会缓冲并推送 DEBUG 及以上。Uvicorn 服务级日志（启动、错误）经 `LoguruHandler` 汇入同一管道；HTTP access 日志默认关闭（`access_log=False`），`uvicorn.access` 不进入 Web /logs。Web Admin 启动时须设 `log_config=None` 并调用 `bridge_uvicorn_loggers()`，否则 Uvicorn 默认 logging 配置会阻断传播。

## JWT 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_ALGORITHM` | `HS256` | JWT 算法 |
| `JWT_EXPIRE_MINUTES` | `1440` | Token 过期时间（分钟） |

## 已弃用的业务环境变量

以下变量在 2.0 中已弃用，启动时会有提示，请改到 Web Admin 配置：

- `LIVE_MONITOR_*`
- `DYNAMIC_MONITOR_*`
- `STATUS_CHECK_*`
- `BILIBILI_COOKIE`（改到 Web Admin → 设置 → B 站账号）
- `SUPERUSERS`（改到 Web Admin → 设置 → 机器人）
- `NOTIFY_GROUPS`（改到各监控页面的目标群/好友映射）

详见 [1.x 迁移指南](./migration-2.0)。
