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

`bot.py` 在创建客户端之前，将 aiohttp、urllib、HTTPX / NoneBot HTTPX 和 websockets 的默认客户端 TLS 信任库统一为随应用安装的 certifi Mozilla CA 包，包含 HTTPS 代理的外层连接。Docker、Windows 包和源码启动均保留证书链与主机名校验，避免重新信任宿主机中已被撤销信任的根证书。

默认客户端不再从操作系统、`SSL_CERT_FILE`、`SSL_CERT_DIR` 或 HTTPX 的 CA 环境覆盖加载附加根证书。开发调用方如需连接私有 CA 服务或代理，应显式传入仅包含所需信任的 `SSLContext`；服务端客户端证书验证用途和显式 CA 参数仍保留。代理地址、认证与路由环境设置继续生效。

Playwright 的 Node 驱动及浏览器下载使用同一 certifi CA 包，并强制开启证书校验。截图与抖音扫码使用完整 Chromium 的独立临时配置目录，按公钥拒绝本次 emSign 事件披露的中间 CA（含交叉签名）；每次启动先通过本机的允许 / 拒绝证书检查，再加载业务页面或 Cookie。配置不兼容或检查失败时停止浏览器功能，不回退为忽略证书错误。策略不修改宿主机信任库。

源码安装请使用 `python scripts/secure_pip.py install -r requirements.txt` 与 `python scripts/playwright_install.py install chromium`。安装器按公钥身份过滤事件涉及的四个根证书及八个受影响中间 CA，包括重编码和不同自签名的信任锚，在过滤后的 CA 包上安全升级 pip 至至少 26.2.2，并关闭 pip 对系统信任库的自动合并。私有构建 CA 可通过 `PIP_CERT` 提供（仍会过滤受影响公钥）；索引和代理可用命令行参数或环境变量配置。安装器不读取用户 / 系统 pip 配置，也不接受跳过 TLS 校验的覆盖。镜像与 Windows 构建会检查实际打包的 CA、Node 和 Chromium 行为。

前端与文档依赖使用 `node ../scripts/secure_npm.cjs ci`（在 `web/` 或 `docs/` 内执行），构建使用 `node ../scripts/secure_npm.cjs run build`。需 Node.js 22.23.4 或支持 CA API 的较新 LTS 版本。npm 包装器过滤默认及 `NODE_EXTRA_CA_CERTS` 信任中的事件公钥；显式 `cafile` / `ca` 保持替换默认信任库的语义并接受同样过滤。registry、代理和认证配置继续由 npm 读取；`strict-ssl` 和 Node 证书校验被强制开启，生命周期子进程沿用同一过滤后的 CA 包。

requirements 和 npm 生命周期脚本属于可信构建输入，需按代码审查；不得在 requirements 中加入 `--trusted-host` 等跳过证书校验的选项。

事件证书样本及来源记录在仓库 `tests/fixtures/ca_incident/README.md`，来自 [事件披露站点](https://emudhra.we-have-a-problem.com/)。浏览器证书数据库目前使用 Chromium schema v1；升级 Playwright / Chromium 时须执行 `tests/test_browser_security.py` 和 `scripts/check_tls_artifacts.py`。

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
