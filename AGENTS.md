# AGENTS.md

面向 AI Agent 与协作者的仓库指南。详细用户文档见 [README.md](README.md)、[docs/](docs/)（在线：https://cyxc1124.github.io/cyxcbot/）。

## 项目概览

**机器草（cyxcbot）**：基于 NoneBot2 的 QQ 机器人，专注 B 站直播/动态监控与群消息推送。2.0 起业务配置走 **Web Admin + 数据库**，环境变量仅保留启动级项。

| 组件 | 技术 |
|------|------|
| 机器人 | NoneBot2 + OneBot V11 |
| Web Admin API | FastAPI（`admin/`） |
| 前端 | React + TypeScript + Tailwind（`web/`） |
| 数据库 | SQLAlchemy + Alembic 迁移（`shared/db/`） |
| 截图 | Playwright + Chromium |

入口：`bot.py` → `nonebot.init()` → 加载 `plugins/`、`admin/startup.py` 启动 Web Admin。

## 目录结构

```
bot.py              # 主入口
admin/              # FastAPI、JWT 鉴权、REST/WS API
shared/             # DB、ConfigService、策略、通知、B 站登录、日志广播
plugins/            # NoneBot 插件（每目录一个 __init__.py）
utils/              # B 站 API、截图等无 NoneBot 依赖的工具
web/                # 管理面板前端（独立 npm 项目）
docs/               # 文档站（Docusaurus）
scripts/            # Windows 打包等
tests/              # pytest
deploy/             # Docker Compose / Helm
```

数据流：Web Admin ↔ `admin/` ↔ `shared/db` ↔ 各 `plugins/` ↔ OneBot 协议端。

### 插件

| 插件 | 职责 |
|------|------|
| `dynamic_monitor` | UP 主动态轮询推送；`最新动态`/`置顶动态`/`#提取` |
| `live_monitor` | 直播开播/下播（WebSocket + API 轮询） |
| `video_monitor` | 群内 `最新视频`/`最新投稿` **命令查询**（非自动推送；新投稿推送见 `dynamic_monitor`） |
| `bilibili_link_parser` | 群/好友 B 站链接与 QQ 小程序自动解析 |
| `group_guard` / `private_guard` | 入站消息总开关（不影响监控主动推送） |
| `status_check` | `/status` 运行状态查询与权限控制 |

### Admin ↔ Plugin 边界

- **`admin/` 不得直接 `import plugins.*`**（除 `admin/services/monitor_bridge.py`、`onebot_bridge.py` 等桥接模块）。
- Web Admin 查监控状态、触发热重载、读群/好友列表均走上述 bridge。

## 开发与测试

- 使用仓库根目录 `.venv/`，勿用系统全局 Python。不存在时：`python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt`
- 格式化/检查：`./.venv/bin/ruff check .`、`./.venv/bin/ruff format .`
- 测试：`./.venv/bin/pytest`
- 本地启动：`./.venv/bin/python bot.py`；前端另开终端 `cd web && npm run dev`
- 前端构建/类型检查：`cd web && npm run build`
- 文档站：`cd docs && npm start`（预览）/ `npm run build`
- `bot.py` 有 intentional E402（`nonebot.init()` 之后的 import），ruff 已忽略

## 配置约定

**环境变量**（见 `env.example`）：`HOST`/`PORT`、`COMMAND_START`/`COMMAND_SEP`、`WEB_*`、`WEB_SECRET_KEY`、`SQLALCHEMY_DATABASE_URL`、`LOG_LEVEL` 等启动级配置。

**业务配置**（监控映射、B 站 Cookie、模板、权限等）：存数据库，经 Web Admin 管理。通过 `shared.config.service.get_config_service()` 读取，**不要**新增已弃用环境变量：

- 前缀：`LIVE_MONITOR_*`、`DYNAMIC_MONITOR_*`、`STATUS_CHECK_*`
- 精确：`BILIBILI_COOKIE`、`SUPERUSERS`、`NOTIFY_GROUPS`

**插件读配置的标准模式**：

1. `Config.from_service()` 从 `get_config_service().get_snapshot()` 取快照
2. 需热重载的插件注册 `get_config_service().register_reload_callback(...)`（见 `dynamic_monitor`、`live_monitor`、`video_monitor`、`bilibili_link_parser`）
3. 超级用户由 `shared/config/nonebot_superusers.py` 从 DB 同步到 NoneBot

数据库迁移在 `shared/db/migrations/`；启动时由 `nonebot.init(alembic_startup_check=False)` 自动应用。

## 代码风格

- **最小改动**：只改任务相关代码，不扩 scope、不加未请求的抽象。
- **沿用现有模式**：命名、import 顺序、错误处理方式与周边文件保持一致。
- **注释**：仅解释非显而易见的业务/技术细节；不自解释代码。
- **测试**：非平凡逻辑留最小可运行检查（`tests/` 里 pytest）；一行能搞定的不用框架。
- **安全**：JWT 密钥、Cookie、数据库凭证等**不得**写入日志或硬编码。
- **提交**：仅在用户明确要求时 `git commit`；不主动 push。

## 日志规范（NoneBot / loguru）

本项目使用 NoneBot 内置的 loguru logger。Web Admin `/logs` 通过 `shared/logging/broadcast.py` 订阅同一条 logger 输出。

### 必须

```python
from nonebot.log import logger

logger.info("服务已启动")
logger.warning("未配置 Cookie，部分接口可能受限")
logger.debug("房间 {} 轮询完成", room_id)  # 高频路径优先占位符，避免 f-string 无谓求值
```

异常栈：

```python
try:
    ...
except Exception:
    logger.opt(exception=True).error("处理动态查询失败")
```

### 禁止

```python
# ❌ 不要用 print
print("debug")

# ❌ 不要用标准库 logging（不会进 NoneBot 格式，也不会进 Web 日志广播）
import logging
logger = logging.getLogger(__name__)

# ❌ 不要手写 traceback
import traceback
logger.error(f"错误: {traceback.format_exc()}")
```

若第三方库走 stdlib `logging`，在入口用 `LoguruHandler` 桥接（见 [NoneBot 日志文档](https://nonebot.dev/docs/appendices/log)），不要另起一套 handler。

### 级别选用

| 级别 | 用途 |
|------|------|
| `debug` | 轮询细节、单次检查、开发诊断 |
| `info` | 启动、配置变更、用户可见操作结果 |
| `success` | 可选；重大里程碑（插件加载完成等） |
| `warning` | 可降级继续、配置缺失、重试 |
| `error` | 单条失败、需关注的异常 |
| `critical` | 极少用；进程级致命问题 |

周期性监控（直播/动态轮询）用 `shared/monitor/check_cycle.py` 的 `CheckCycleLogger` 汇总每轮结果，避免对每个目标单独 `info`。

### 日志级别配置

- 由环境变量 **`LOG_LEVEL`** 控制（默认 `INFO`），NoneBot 在 `nonebot.init()` 时读取，**仅过滤终端 stdout 输出**。
- Web Admin `/logs` 通过 `install_log_broadcast()` 注册的 sink 固定为 `DEBUG` 级别：即使 `LOG_LEVEL=INFO/WARNING`，终端不显示 DEBUG，Web 日志页仍会缓冲并推送 DEBUG 及以上。
- `bot.py` 的 `configure_logging()` 仅调节 stdlib 第三方库（如 `aiohttp`、`playwright`）噪声，**不**改变 `nonebot.log.logger` 的过滤级别。
- 第三方 stdlib 日志经 `bot.py` 中的 `LoguruHandler` 汇入 NoneBot/loguru 管道，再进入 Web 广播。Uvicorn 启动时使用 `log_config=None`、`access_log=False` 并调用 `bridge_uvicorn_loggers()`（仅桥接 `uvicorn`/`uvicorn.error`/`uvicorn.asgi`，`uvicorn.access` 不进入 Web /logs），勿在 `broadcast.py` 重复挂载 uvicorn handler。
- 磁盘持久化由 `shared/logging/file_sink.py` 的 `install_file_log_sink()` 注册 rotating file sink（默认 `data/logs/cyxcbot.log`，见 `LOG_FILE_*` 环境变量）；与 Web 环形缓冲独立，级别由 `LOG_FILE_LEVEL` 控制。

### 敏感信息

- Cookie、Token、密码：只记录「是否已配置」或计数，不记录值。
- 启动环境变量脱敏见 `bot.py` 的 `_format_env_value()` / `_mask_database_url()`，新增启动日志时沿用同样规则。

## 常见修改入口

| 任务 | 位置 |
|------|------|
| 新增/改监控逻辑 | `plugins/<name>/` |
| 共享 DB 模型 | `shared/db/models.py` + 新 migration |
| 运行时配置读写 | `shared/config/service.py` |
| 消息模板默认值 | `shared/config/message_templates.py` |
| 链接解析策略 | `shared/config/link_parser_policy.py` |
| 群/好友/状态查询策略 | `shared/group_policy.py`、`private_policy.py`、`status_check_policy.py` |
| 通知发送 | `shared/notify/delivery.py` |
| B 站扫码登录 | `shared/bilibili/qrcode_login.py` |
| Cookie 加密 | `shared/security/crypto.py` |
| Admin↔监控桥接 | `admin/services/monitor_bridge.py` |
| Admin↔OneBot 桥接 | `admin/services/onebot_bridge.py` |
| Web API | `admin/api/v1/` |
| B 站 HTTP 封装 | `utils/bilibili_api/` |
| 截图 | `utils/screenshot/` |
| 前端页面 | `web/src/pages/` |

插件细节见各 `plugins/*/README.md`；前端见 [web/README.md](web/README.md)；部署见 [deploy/README.md](deploy/README.md)。
