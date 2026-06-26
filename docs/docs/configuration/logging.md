---
sidebar_position: 4
---

# 日志

机器草（cyxcbot）使用 NoneBot 内置的 loguru 管道。同一条日志流可同时输出到 **终端**、**Web 管理面板** 与 **磁盘文件**，三者级别与保留策略各自独立。

## 输出通道

| 通道 | 用途 | 保留 | 级别控制 |
|------|------|------|----------|
| 终端 stdout | 本地 / `docker compose logs` 实时查看 | 不保留 | `LOG_LEVEL` |
| Web `/logs` | 浏览器实时浏览 | 内存约 **2000** 条 | 服务端缓冲 `DEBUG`+；页面默认筛选 **INFO**+ |
| 磁盘文件 | 排障、跨重启追溯 | 默认 **7 天**（可配置） | `LOG_FILE_LEVEL`（默认同 `LOG_LEVEL`） |

```
插件 / 第三方库
    → nonebot.log.logger (loguru)
        ├─ 终端（受 LOG_LEVEL 过滤）
        ├─ Web 广播 sink → /logs WebSocket（固定 DEBUG+，环形缓冲）
        └─ 文件 sink → data/logs/（可禁用）
```

Uvicorn（Web Admin）的服务级日志（启动、错误）经同一管道汇入；HTTP **access** 日志默认关闭，不会刷屏 Web `/logs`。

## 环境变量

完整列表见 [环境变量](./env-vars#日志)。常用项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | `INFO` | 仅过滤**终端**输出 |
| `LOG_FILE_ENABLED` | `true` | `false` 禁用磁盘日志 |
| `LOG_FILE_PATH` | `data/logs/cyxcbot.log` | 路径**模板**（见下文文件名规则） |
| `LOG_FILE_LEVEL` | 同 `LOG_LEVEL` | 写入文件的最低级别 |
| `LOG_FILE_ROTATION` | `10 MB` | 单次运行内 active 文件切分条件（支持 loguru 大小/时间，如 `50 MB`、`1 day`） |
| `LOG_FILE_RETENTION` | `7 days` | 过期日志保留时长（格式：`7 days`、`30 days` 等） |

示例（`.env`）：

```bash
LOG_LEVEL=INFO
LOG_FILE_ENABLED=true
LOG_FILE_PATH=data/logs/cyxcbot.log
# LOG_FILE_LEVEL=DEBUG      # 需要更详细的磁盘日志时单独打开
# LOG_FILE_ROTATION=10 MB
# LOG_FILE_RETENTION=30 days
```

## 磁盘日志

默认启用。日志目录为 `data/logs/`，与 SQLite 数据库同属 `data/`，Docker Compose / Helm 挂载 `data/` 卷后**重启仍会保留**。

### 每次启动新建文件

`LOG_FILE_PATH` 是模板，进程每次启动会写入新文件：

```text
data/logs/cyxcbot.2026-06-26_14-30-52.123.log
```

格式：`{stem}.{YYYY-MM-DD_HH-MM-SS.mmm}.log`

若仍存在旧版 plain `cyxcbot.log`（无时间戳），首次启动时会自动改名为 `cyxcbot.archived-2026-06-26_14-30-52.123.log`。

### 单次运行内切分（10 MB）

同一次运行中，active 文件超过 `LOG_FILE_ROTATION` 时由 loguru 切分：

| 角色 | 文件名示例 |
|------|------------|
| 当前写入 | `cyxcbot.2026-06-26_14-30-52.123.log` |
| 切分归档 | `cyxcbot.2026-06-26_14-30-52.123.2026-06-26_15-00-00_182160.log` |

切分后继续写入同名 active 文件。会话内切出的旧片段也受 `LOG_FILE_RETENTION` 约束。

### 过期清理

- **下次启动**时：删除目录内超过 `LOG_FILE_RETENTION` 的、由本 sink 管理的会话/归档文件。
- **运行中切分**时：loguru 按 `retention` 清理同 sink 产生的旧片段。
- 清理**不会**误删同目录下其他日志（如 `cyxcbot.access.log`），仅匹配本 sink 的时间戳命名规则。

### 查看文件日志

```bash
# 本地
tail -f data/logs/cyxcbot.*.log

# Docker Compose（数据在宿主机 ./data）
tail -f deploy/compose/data/logs/cyxcbot.*.log

# 容器标准输出（与磁盘文件无关）
docker compose logs -f cyxcbot
```

## Web 管理面板 `/logs`

- 实时 WebSocket 推送，支持按 `DEBUG` / `INFO` / `WARNING` / `ERROR` 筛选（**默认 `INFO`**）。
- 打开页面时先拉取约 **500** 条历史，浏览器最多展示约 **1500** 条。
- 服务端缓冲收录 `DEBUG` 及以上（终端在 `LOG_LEVEL=INFO` 时不显示 `DEBUG`）；要在页面上看 `DEBUG`，需将级别下拉框改为 `DEBUG`。
- 需管理员登录；重启后 Web 缓冲清空。查历史请用磁盘文件或 `docker compose logs`。

详见 [页面说明 — 日志](../web-admin/pages#日志-logs)。

## 开发约定

- 业务代码使用 `from nonebot.log import logger`，不要用 `print` 或 stdlib `logging`。
- 高频路径（轮询、单次检查）优先 `logger.debug`；周期性监控用 `CheckCycleLogger` 汇总，避免逐条 `info`。
- Cookie、Token 等敏感信息只记「是否配置」，不记值。

实现位置：

| 模块 | 职责 |
|------|------|
| `shared/logging/broadcast.py` | Web 环形缓冲与 WebSocket 广播 |
| `shared/logging/file_sink.py` | 磁盘会话日志与清理 |
| `bot.py` | stdlib → loguru 桥接、安装 sink |
| `admin/api/v1/logs.py` | `/logs/recent` 与 `/ws/logs` API |

## 故障排查

| 现象 | 建议 |
|------|------|
| 终端无 DEBUG | 正常；设 `LOG_LEVEL=DEBUG`、Web `/logs` 级别选 `DEBUG`，或设 `LOG_FILE_LEVEL=DEBUG` |
| Web `/logs` 无新行 | 检查 WebSocket 连接状态；确认 `WEB_ADMIN_ENABLED` 未禁用 |
| 磁盘无文件 | 确认 `LOG_FILE_ENABLED=true`；检查 `data/logs/` 权限 |
| `data/` 磁盘占满 | 缩短 `LOG_FILE_RETENTION`、提高 `LOG_FILE_LEVEL` / `LOG_LEVEL` 减少写入；确认 `data/` 卷已挂载 |
| 需要 HTTP 访问审计 | 在 Nginx / 反向代理侧记录 access log；本程序默认不写 Uvicorn access |
