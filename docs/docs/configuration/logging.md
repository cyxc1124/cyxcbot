---
sidebar_position: 4
---

# 日志

机器草（cyxcbot）使用 NoneBot 内置的 loguru 管道。同一条日志流可同时输出到 **终端**、**Web 管理面板** 与 **磁盘文件**，三者级别与保留策略各自独立。

## 输出通道

| 通道 | 用途 | 保留 | 级别控制 |
|------|------|------|----------|
| 终端 stdout | 本地 / `docker compose logs` 实时查看 | 不保留 | Web 保存值；未保存时用 `LOG_LEVEL` |
| Web `/logs` | 浏览器实时浏览 | `INFO`+、`DEBUG` 各最多 **2000** 条 | 服务端缓冲 `DEBUG`+；页面默认筛选 **INFO**+ |
| 磁盘文件 | 排障、跨重启追溯 | 默认 **7 天**（可配置） | Web 保存值；未保存时用 `LOG_FILE_LEVEL`（默认同 `LOG_LEVEL`） |

```
插件 / 第三方库
    → nonebot.log.logger (loguru)
        ├─ 终端（独立的运行时级别）
        ├─ Web 广播 sink → /logs SSE（固定 DEBUG+，环形缓冲）
        └─ 文件 sink → data/logs/（可禁用）
```

Uvicorn（Web Admin）的服务级日志（启动、错误）经同一管道汇入；HTTP **access** 日志默认关闭，不会刷屏 Web `/logs`。

NoneBot 每条入站事件会打一条 SUCCESS dump，并为每个命中的 Matcher 打「will be handled / running complete」。这些**只保留在终端和磁盘日志**，不进入 Web `/logs` 环形缓冲，避免群聊刷屏干扰排障。

## 环境变量

完整列表见 [环境变量](./env-vars#日志)。常用项：

`LOG_LEVEL` 和 `LOG_FILE_LEVEL` 是各通道尚未在 Web 保存时的默认值。进入 Web Admin → 运行日志 → **显示选项 → 输出级别**，可分别选择终端与文件级别并保存，立即生效且重启后保留；保存值优先于环境变量。两者支持 `TRACE`、`DEBUG`、`INFO`、`SUCCESS`、`WARNING`、`ERROR`、`CRITICAL`。修改终端级别不会同时修改文件级别。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | `INFO` | **终端**的初始最低输出级别 |
| `LOG_FILE_ENABLED` | `true` | `false` 禁用磁盘日志 |
| `LOG_FILE_PATH` | `data/logs/cyxcbot.log` | 路径**模板**（见下文文件名规则） |
| `LOG_FILE_LEVEL` | 同 `LOG_LEVEL` | 写入文件的初始最低级别 |
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

- 实时 SSE 推送，以独立胶囊多选 `DEBUG` / `INFO` / `SUCCESS` / `WARNING` / `ERROR` / `CRITICAL`（**默认 INFO 及以上**）。可按消息、模块、级别或时间搜索；均只影响当前 Web 视图。
- 点击工具栏的 **显示选项**，可使用「开发」（全部可用级别、2000 行、换行）、「运维」（默认；INFO 及以上、1000 行、换行）、「精简」（WARNING 及以上、500 行、不换行）预设，也可单独调整显示行数与自动换行。
- 显示选项内的 **输出级别**以单选胶囊分别控制终端与文件日志，通过管理员鉴权的 `PATCH /api/v1/settings` 保存 `log_level`、`log_file_level` 到数据库并热重载；上方 **Web 显示级别**不会修改上述保存值。
- 文件级别调整复用当前日志文件，不重新切分或清理日志。`LOG_FILE_ENABLED=false` 时不会因修改级别而启用文件日志；路径、切分与保留参数仍由启动配置控制。
- 打开页面时先拉取最多 **2000** 条历史，浏览器最多展示 **2000** 条。
- **导出当前视图**下载当前筛选和行数限制内的全部日志，包含尚未滚动到的行，以 UTF-8 `.log` 文件保存完整时间、级别、模块及多行消息。导出不包含服务器磁盘日志或 Web 缓冲未收录的 TRACE。
- 前端通过 `fetch` 携带管理员 Bearer Token；断线后间隔 **3 秒**重连，回放当前级别的最近缓存并按会话和日志 ID 去重。鉴权失败停止重试，登录过期时跳转登录页。
- 暂停只停止显示更新，仍接收并保留最多 **2000** 条待显示日志；清空仅影响当前显示。
- 服务端缓冲收录 `DEBUG` 及以上（终端级别为 `INFO` 时不显示 `DEBUG`）；要在页面上看 `DEBUG`，勾选该级别或使用「开发」预设。默认视图仍按 INFO 门槛查询，避免 DEBUG 洪峰挤占 INFO 历史。
- 入站事件 dump 与 Matcher 调度行只出现在终端 / 磁盘，不进入本页。
- 需管理员登录；重启后 Web 缓冲清空。查历史请用磁盘文件或 `docker compose logs`。

SSE 接口为 `GET /api/v1/logs/stream`，与 OneBot 的 HTTP / WebSocket 接入独立。FastAPI 在空闲时每 **15 秒**发送心跳，并设置 `Cache-Control: no-cache`、`X-Accel-Buffering: no`。反向代理需允许流式响应，避免对该接口缓冲，读取超时应大于心跳间隔。断线时间过长或日志量超过缓存容量时，较早日志无法补发。

详见 [页面说明 — 日志](../web-admin/pages#日志-logs)。

## 开发约定

- 业务代码使用 `from nonebot.log import logger`，不要用 `print` 或 stdlib `logging`。
- 高频路径（轮询、单次检查）优先 `logger.debug`；周期性监控用 `CheckCycleLogger` 汇总，避免逐条 `info`。
- Cookie、Token 等敏感信息只记「是否配置」，不记值。

高频日志优先使用占位符（如 `logger.debug("房间 {} 轮询完成", room_id)`），避免 f-string 无谓求值。异常栈交给 loguru，不要手写 `traceback.format_exc()`：

```python
try:
    ...
except Exception:
    logger.opt(exception=True).error("处理动态查询失败")
```

| 级别 | 用途 |
|------|------|
| `debug` | 轮询细节、单次检查、开发诊断 |
| `info` | 启动、配置变更、用户可见操作结果 |
| `success` | 可选；重大里程碑，如插件加载完成 |
| `warning` | 可降级继续、配置缺失、重试 |
| `error` | 单条失败、需关注的异常 |
| `critical` | 极少用；进程级致命问题 |

第三方库使用 stdlib `logging` 时，在入口通过 `LoguruHandler` 桥接到 NoneBot/loguru 管道（见 [NoneBot 日志文档](https://nonebot.dev/docs/appendices/log)），不要另起一套 handler。`bot.py` 的 `configure_logging()` 仅调节第三方库噪声；已有的第三方日志源级别限制不会被输出级别设置解除。

Uvicorn 启动时使用 `log_config=None`、`access_log=False`，并调用 `bridge_uvicorn_loggers()`，只桥接 `uvicorn`、`uvicorn.error`、`uvicorn.asgi`；`uvicorn.access` 不进入 Web `/logs`。勿在 `broadcast.py` 重复挂载 Uvicorn handler。

新增启动/诊断日志时，沿用 `shared/security/database_url.py` 的 `mask_database_url()` 与 `bot.py` 的 `_format_env_value()` 脱敏规则。周期性监控汇总器位于 `shared/monitor/check_cycle.py`。

实现位置：

| 模块 | 职责 |
|------|------|
| `shared/logging/broadcast.py` | Web 环形缓冲与异步订阅广播 |
| `shared/logging/file_sink.py` | 磁盘会话日志与清理 |
| `shared/logging/levels.py` | 终端与文件的独立运行时级别、配置热重载 |
| `bot.py` | stdlib → loguru 桥接、安装 sink |
| `admin/api/v1/logs.py` | `/logs/recent` 与 `/logs/stream` SSE API |

## 故障排查

| 现象 | 建议 |
|------|------|
| 终端无 DEBUG | 在 Web `/logs` → 显示选项 → 输出级别中将终端改为 `DEBUG` 并保存；页面查看 DEBUG 需另选 Web 显示级别 |
| Web `/logs` 无新行 | 检查 SSE 连接状态与反向代理缓冲；确认 `WEB_ADMIN_ENABLED` 未禁用 |
| 磁盘无文件 | 确认 `LOG_FILE_ENABLED=true`；检查 `data/logs/` 权限 |
| `data/` 磁盘占满 | 在 Web 提高文件日志级别减少写入，或缩短 `LOG_FILE_RETENTION` 后重启；确认 `data/` 卷已挂载 |
| 需要 HTTP 访问审计 | 在 Nginx / 反向代理侧记录 access log；本程序默认不写 Uvicorn access |
