# AGENTS.md

面向 AI Agent 与协作者的仓库指南。详细用户文档见 [README.md](README.md)、[docs/](docs/)（在线：https://cyxc1124.github.io/cyxcbot/）。

## 项目概览

**机器草（cyxcbot）**：基于 NoneBot2 的 QQ 机器人，支持 OneBot V11 与官方 QQ Bot。Web Admin 使用 FastAPI（`admin/`）和 React + TypeScript + Tailwind（`web/`）；数据库使用 SQLAlchemy + Alembic（`shared/db/`），截图使用 Playwright + Chromium。

入口：`bot.py` → `nonebot.init()` → 加载 `plugins/`、`admin/startup.py` 启动 Web Admin。业务配置走 **Web Admin + 数据库**，环境变量仅保留启动级项。

数据流：Web Admin ↔ `admin/` ↔ `shared/db` ↔ 各 `plugins/` ↔ OneBot 协议端 / 官方 QQ Bot。官方凭证仅存数据库（`official_qq_*`），经 `shared/adapter/official_runtime.py` 热连接；数字 QQ 号走 OneBot，openid 走官方 Bot。`rust_player` / `rust_rcon` / `group_special_title` 仍仅 OneBot。

官方 Bot 默认使用 Webhook（`/qq/webhook`，机器人端口默认 8080）。动态、直播和 X 监控支持官方目标投递；主动能力以 QQ 平台策略及回执为准。动态/直播保存消息快照，X 保存目标和分段进度（重试仍需重新获取推文及媒体）。命令回复走 `send_event_message()`，由 QQ 适配器维护事件回复序号；官方群被动回复最多五次、C2C 四次，解析插件须预先安排媒体和文案预算。

`video_monitor` 仅负责最新视频命令查询，新投稿自动推送在 `dynamic_monitor`；`group_guard` / `private_guard` 控制入站消息，不影响监控主动推送。其余插件职责和用法按需查看对应 `plugins/*/README.md` 或 [插件文档](docs/docs/plugins/)。

## 工作范围与完成条件

- 只读取当前任务需要的代码和文档；下方入口用于按需定位。
- 完成请求所需的调用方、测试和文档调整，修复本次改动引入的问题，完成相关验证后再交付；未解决的阻塞明确报告。
- 保留用户已有改动，只改任务相关代码；沿用周边命名、错误处理和接口，不添加未请求的抽象。
- 注释仅解释代码本身无法表达的原因。行为变更按风险补最小回归检查，不以代码行数判断是否需要测试。
- JWT 密钥、Cookie、Token、数据库凭证等不得写入日志或硬编码。

### Admin ↔ Plugin 边界

- **`admin/` 不得直接 `import plugins.*`**（除 `admin/services/monitor_bridge.py`、`onebot_bridge.py` 等桥接模块）。
- Web Admin 查监控状态、触发热重载、读群/好友列表均走上述 bridge。

## 开发与测试

- 使用 **Python 3.14** 与仓库根目录 `.venv/`，勿用系统全局 Python 运行项目。不存在时：`python3.14 -m venv .venv && ./.venv/bin/pip install -r requirements.txt`；已有环境可用 `./.venv/bin/python --version` 确认版本。
- 按改动影响选择下列检查，不要求每次全跑；格式化仅覆盖本次修改文件。涉及跨模块行为或发版时按影响扩大验证范围。

| 改动 | 验证入口 |
|------|----------|
| Python | `./.venv/bin/ruff check <相关文件>`；`./.venv/bin/ruff format <修改文件>`；`./.venv/bin/pytest tests/<相关测试文件>` |
| 前端行为 | `cd web && npm test -- <相关测试文件>`（Vitest）；完整前端测试为 `npm test` |
| 前端构建/类型 | `cd web && npm run build` |
| 文档站 | `cd docs && npm run build`；普通 Markdown 修改检查内容和链接即可 |

- Python 测试在 `tests/`；前端测试沿用 `web/` 的 Vitest。需要完整 Python 回归时运行 `./.venv/bin/pytest`。
- 本地启动：`./.venv/bin/python bot.py`；前端 `cd web && npm run dev`；文档预览 `cd docs && npm start`。
- 本地验证使用隔离数据库和测试目标；`bot.py` 会连接配置的数据库并执行迁移，不作为无副作用的检查命令。
- `bot.py` 的 E402 是 `nonebot.init()` 后导入所需，Ruff 已忽略。

## 配置约定

**环境变量**（见 `env.example`）：`HOST`/`PORT`、`COMMAND_START`/`COMMAND_SEP`、`WEB_*`、`WEB_SECRET_KEY`、`SQLALCHEMY_DATABASE_URL`、`LOG_LEVEL` 等启动级配置。

**业务配置**（监控映射、B 站 Cookie、模板、权限等）：存数据库，经 Web Admin 管理。通过 `shared.config.service.get_config_service()` 读取，**不要**新增已弃用环境变量：

- 前缀：`LIVE_MONITOR_*`、`DYNAMIC_MONITOR_*`、`STATUS_CHECK_*`
- 精确：`BILIBILI_COOKIE`、`SUPERUSERS`、`NOTIFY_GROUPS`

**插件读配置的标准模式**：

1. `Config.from_service()` 从 `get_config_service().get_snapshot()` 取快照
2. 需热重载的插件注册 `get_config_service().register_reload_callback(...)`，沿用所改插件的现有模式
3. 超级用户由 `shared/config/nonebot_superusers.py` 从 DB 同步到 NoneBot

数据库迁移在 `shared/db/migrations/`；启动时 `nonebot.init(alembic_startup_check=True)` 经 Alembic **upgrade** 应用（勿用 sync 模式，模型变更失败时可能删表重建）。

**新增改表结构的 migration 时，须在 `shared/db/alembic_repair.py` 的 `infer_alembic_revision()` 登记可唯一识别的表/列特征。** 修改迁移或启动修复时阅读 [数据库迁移说明](shared/db/README.md)；不要改写非空的健康 `alembic_version`，也不要在未确认历史部署迁移完成前删除修复代码。

## 提交与发布

- 仅在用户明确要求时 `git commit`；推送、合并、发版和分支清理在用户已授权的范围内执行，已有授权无需重复确认。修改 Helm 文件不代表获得现网部署授权。
- 提交格式为 `<type>: <中文说明>`，可加范围，例如 `fix(auth): 修复会话过期判断`。保留 `feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`、`revert` 等 type 前缀。
- 功能分支通过 PR / MR 合入 `develop`，不得直接推 `develop` 或 `main`（下述 GitLab 同步例外除外）。发版通过 `develop` → `main` 的 PR / MR，合并后才在 `main` 打 annotated tag；只改 CI 不打发行 tag。
- GitHub PR 合入 `develop` 后，允许将其已合并结果快进同步到 GitLab `develop`，无需另开 MR；先同步两端，再清理功能分支。分叉或无法快进时停止并询问，不强推。
- 涉及合并后同步、发版或 Helm 变更时阅读 [维护者发布流程](deploy/README.md#维护者发布流程)，保留双端发布、仓内与仓外 chart 版本同步及现网镜像约定；不得把现网拉取密钥拷回本仓。

## 日志规范（NoneBot / loguru）

- 业务日志使用 `from nonebot.log import logger`，不要用 `print` 或另建 stdlib logger；异常用 `logger.opt(exception=True).error(...)`，不要手写 traceback。
- 高频路径使用占位符和 `debug`；周期性监控用 `shared/monitor/check_cycle.py` 的 `CheckCycleLogger` 汇总，避免逐目标 `info`。
- Cookie、Token、密码只记录是否配置或计数；启动/诊断脱敏沿用 `mask_database_url()` 与 `bot.py` 的 `_format_env_value()`。
- 修改日志管道、第三方桥接或级别过滤时阅读 [日志文档](docs/docs/configuration/logging.md)。保留终端、Web、磁盘的独立过滤行为，勿重复挂载 Uvicorn handler。

## 常见修改入口

| 任务 | 位置 |
|------|------|
| 新增/改监控逻辑 | `plugins/<name>/` |
| 共享 DB 模型 | `shared/db/models.py` + 新 migration |
| 运行时配置读写 | `shared/config/service.py` |
| 消息模板默认值 | `shared/config/message_templates.py` |
| 链接解析策略 | `shared/config/link_parser_policy.py` |
| 群/好友/状态查询策略 | `shared/group_policy.py`、`private_policy.py`、`status_check_policy.py` |
| 通知发送 | `shared/notify/delivery.py`；双栈投递见 `shared/adapter/outbound.py` |
| 官方 QQ Bot | `shared/adapter/`（凭证热连接 `official_runtime.py`） |
| B 站扫码登录 | `shared/bilibili/qrcode_login.py` |
| Cookie 加密 | `shared/security/crypto.py` |
| Admin↔监控桥接 | `admin/services/monitor_bridge.py` |
| Admin↔OneBot 桥接 | `admin/services/onebot_bridge.py` |
| Web API | `admin/api/v1/` |
| B 站 HTTP 封装 | `utils/bilibili_api/` |
| X HTTP 封装 | `utils/x_api/` |
| 截图 | `utils/screenshot/` |
| 前端页面 | `web/src/pages/` |
| Helm（仓内） | `deploy/helm/` |
| Helm（现网，发版改版本） | `../helm-chart/cyxcbot-chart`（相对本仓根；镜像 `registry.gitlab.cyxc.club/cyxc1124/cyxcbot`，勿提交密钥） |

插件细节见各 `plugins/*/README.md`；前端见 [web/README.md](web/README.md)；部署见 [deploy/README.md](deploy/README.md)。
