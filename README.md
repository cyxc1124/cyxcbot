<p align="center">
  <img src="web/public/brand-avatar.png" alt="机器草" width="120" />
</p>

<h1 align="center">机器草 cyxcbot</h1>

<p align="center">
  基于 <a href="https://nonebot.dev/">NoneBot2</a> 的 QQ 机器人：B 站动态与直播推送、X 推文监控、多平台链接解析，自带 Web 管理面板。
</p>

<p align="center">
  <a href="https://github.com/cyxc1124/cyxcbot/releases"><img src="https://img.shields.io/github/v/release/cyxc1124/cyxcbot" alt="GitHub release" /></a>
  <a href="https://github.com/cyxc1124/cyxcbot/actions/workflows/build-and-push.yml"><img src="https://github.com/cyxc1124/cyxcbot/actions/workflows/build-and-push.yml/badge.svg?branch=main" alt="Build" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.15-3776AB?logo=python&amp;logoColor=white" alt="Python" /></a>
  <a href="#协议支持"><img src="https://img.shields.io/badge/QQ-OneBot%20V11%20%7C%20%E5%AE%98%E6%96%B9%20Bot-12B7F5" alt="QQ" /></a>
  <a href="https://cyxc1124.github.io/cyxcbot/"><img src="https://img.shields.io/badge/docs-online-2ea44f" alt="Docs" /></a>
</p>

<p align="center">
  <a href="https://cyxc1124.github.io/cyxcbot/">文档</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="https://github.com/cyxc1124/cyxcbot/releases/latest">下载</a> ·
  <a href="https://github.com/cyxc1124/cyxcbot/releases">更新日志</a>
</p>

## 功能

- **B 站动态与直播推送**：新动态、置顶变化、新投稿和开播 / 下播通知，可推送到群聊或私聊；支持多账号扫码登录，查询请求轮换使用。见 [动态监控](docs/docs/plugins/dynamic-monitor.md)、[直播监控](docs/docs/plugins/live-monitor.md)、[账号配置](docs/docs/configuration/web-admin-setup.md#4-配置-b-站账号)。
- **X 推文监控**：订阅博主，推送正文和媒体；需要 X API Bearer Token，可配置出站代理。见 [X 推文监控](docs/docs/plugins/x-monitor.md)。
- **链接解析**：[B 站](docs/docs/plugins/link-parser.md)（多 P 视频回复数字选择分 P，可直接发送视频）、[抖音](docs/docs/plugins/douyin-link-parser.md)（视频、图集、Live 图）、[X](docs/docs/plugins/x-link-parser.md) 推文，按会话设置策略。
- **AI 图片检测**：引用一张图片回复 `ai吗？`，本地校验 C2PA 凭证；配置 OpenAI API Key 后还会检查其支持的 C2PA 与 SynthID 信号。见 [AI 图片检测](docs/docs/plugins/ai-image-detector.md)。
- **命令与会话管理**：最新动态与[最新视频](docs/docs/plugins/video-monitor.md)查询、动态图片提取、[状态查询](docs/docs/plugins/status-check.md)、[群聊](docs/docs/plugins/group-guard.md) / [私聊](docs/docs/plugins/private-guard.md)白名单，以及自定义触发词和消息模板。
- **Rust 服务器与群管理**：[RCON 远控](docs/docs/plugins/rust-rcon.md)、[签到积分与积分商城](docs/docs/plugins/rust-player.md)、[群专属头衔](docs/docs/plugins/group-special-title.md)。
- **Web Admin**：在浏览器中管理订阅、账号、权限、模板、运行日志和连接状态；业务配置存入数据库，保存后热更新。见 [Web Admin](docs/docs/web-admin/overview.md)。

## 协议支持

OneBot V11 与官方 QQ Bot 可以同时在线：数字 QQ 号 / 群号走 OneBot，官方群聊和私聊（openid）走官方 Bot。

| | OneBot V11 | 官方 QQ Bot |
|---|---|---|
| 接入方式 | 协议端（如 NapCat）反向 WebSocket | Webhook（公网 HTTPS） |
| 命令与链接解析 | ✅ | ✅ |
| 动态 / 直播 / X 推送 | ✅ | ✅（以平台权限和实际回执为准） |
| Rust、群专属头衔、AI 图片检测 | ✅ | — |

## 快速开始

以 Docker Compose 为例，使用 GHCR 预构建镜像：

```bash
git clone https://github.com/cyxc1124/cyxcbot.git
cd cyxcbot/deploy/compose

# 仅首次部署时生成密钥。之后升级保留原值，更换会导致已加密的凭证无法解密
echo "WEB_SECRET_KEY=$(openssl rand -hex 32)" > .env

docker compose up -d
```

启动后：

1. 打开 `http://<主机>:8081`，在 `/setup` 创建管理员。未初始化时任何人都能抢先创建，请尽快完成。
2. 接入 QQ，二选一或同时使用：
   - **OneBot**：在协议端配置反向 WebSocket `ws://<主机>:8080/onebot/v11/ws`。
   - **官方 QQ Bot**：在「系统 → 机器人接入」保存凭证，将公网 HTTPS 的 `/qq/webhook` 转发到 **8080** 端口（不是 8081）。
3. 在「B 站 → 账号」扫码登录并添加订阅；在「会话 → 群组 / 好友」中启用需要响应命令和链接解析的会话。

详细步骤见 [快速开始](docs/docs/getting-started/quick-start.md) 和 [Web Admin 初始化与机器人接入](docs/docs/configuration/web-admin-setup.md)。

### 其他部署方式

| 方式 | 适用场景 | 文档 |
|------|----------|------|
| Docker Compose | 单机 / NAS，使用预构建镜像 | [Docker Compose](docs/docs/getting-started/docker-compose.md) |
| Docker | 从源码构建镜像 | [Docker 部署](docs/docs/getting-started/docker.md) |
| Helm | Kubernetes | [Helm 部署](docs/docs/getting-started/helm.md) |
| Windows 可执行包 | Windows 桌面，无需安装 Python | [Windows 部署](docs/docs/getting-started/windows.md) |
| 源码运行 | 开发与调试 | [本地开发](#本地开发) |

Windows 包在 [Releases](https://github.com/cyxc1124/cyxcbot/releases) 下载 `cyxcbot-windows-<版本>.zip`：解压后将 `env.example` 复制为 `.env` 并填写 `WEB_SECRET_KEY`，运行 `cyxcbot.exe`，再打开 `http://localhost:8081`。

## 配置

订阅、账号、权限、模板等业务配置都在 Web Admin 中管理；环境变量只保留启动级配置：

| 变量 | 说明 |
|------|------|
| `HOST`、`PORT` | 机器人监听地址和端口，供 OneBot 与官方 Webhook 使用（`env.example`：`0.0.0.0`、`8080`） |
| `COMMAND_START`、`COMMAND_SEP` | 命令前缀与分隔符（`env.example`：`["/"]`、`["."]`） |
| `WEB_HOST`、`WEB_PORT` | Web Admin 监听地址和端口（默认 `0.0.0.0`、`8081`） |
| `WEB_ADMIN_ENABLED` | 设为 `false` 可禁用 Web Admin |
| `WEB_SECRET_KEY` | 登录签名与敏感配置加密密钥；使用 Web Admin 时必填，至少 32 个字符 |
| `WEB_PUBLIC_ORIGIN` | 反向代理改写 Host 时，填写浏览器访问的源，如 `https://bot.example.com` |
| `SQLALCHEMY_DATABASE_URL` | 数据库连接串（`env.example`：SQLite `data/cyxcbot.db`）；使用 PostgreSQL 需另装匹配的驱动 |
| `LOG_LEVEL` | 日志级别（默认 `INFO`） |

完整列表见 [`env.example`](env.example) 和 [环境变量](docs/docs/configuration/env-vars.md)。升级前备份数据库和 `.env`，并保留原有 `WEB_SECRET_KEY`。从 1.x 升级见 [2.0 迁移说明](docs/docs/configuration/migration-2.0.md)。

## 本地开发

技术栈：NoneBot2（OneBot V11 / 官方 QQ 适配器）、FastAPI、SQLAlchemy + Alembic、React + TypeScript + Tailwind CSS + Vite、Playwright（Chromium）。

需要 **Python 3.15** 和 **Node.js 26 LTS**（26.13.0+，使用 nvm 时在仓库根目录运行 `nvm use`）。依赖请通过仓库的包装脚本安装，它们使用过滤后的 CA 信任库。

```bash
python3.15 -m venv .venv
./.venv/bin/python scripts/secure_pip.py install -r requirements.txt
./.venv/bin/python scripts/playwright_install.py install chromium   # 截图与抖音扫码需要

cp env.example .env   # 填写 WEB_SECRET_KEY，可用下一行命令生成
./.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
./.venv/bin/python bot.py

# 另开终端启动前端开发服务器（http://localhost:5173，API 代理到 8081）
cd web && node ../scripts/secure_npm.cjs ci && node ../scripts/secure_npm.cjs run dev
```

- Windows 下创建虚拟环境：`py -3.15 -m venv .venv`。
- 要在 8081 直接使用管理页面，需要先构建 `web/dist`；开发时也可以只用 Vite 开发服务器。
- `bot.py` 启动时会连接数据库并执行迁移，请使用单独的开发数据库。
- 检查与测试见 [测试](docs/docs/development/testing.md)，目录说明见 [项目结构](docs/docs/development/project-structure.md)，文档站本地预览见 [docs/README.md](docs/README.md)。

## 参与贡献

欢迎提交 Issue 和 Pull Request。功能分支通过 PR 合入 `develop`，提交信息使用 `<type>: <中文说明>` 格式，如 `fix(auth): 修复会话过期判断`。维护者发版流程见 [deploy/README.md](deploy/README.md#维护者发布流程)。

## 项目由来

机器草最初只是给我自己看的主播 **嘉穗Miho** 做的 QQ 群推送工具，把 B 站开播和动态更新及时推到群里，方便粉丝第一时间知道。后来 **Dreadload** 说他用的机器人不好用了，我就给他安利了机器草。为了让更多人用起来，从 2.0.0 起做了一次大改版：增加 Windows 可执行包和 Web 管理面板，业务配置从环境变量迁到数据库。完整经过见 [项目介绍](docs/docs/intro.md)。

## 致谢

- **[嘉穗Miho](https://space.bilibili.com/3493119318297082)** — 机器草最初为她和粉丝群而生
- **Dreadload** — 2.0 改版的直接契机；感谢他的反馈与试用
- **[NoneBot2](https://github.com/nonebot/nonebot2)** — 机器人开发框架

### 参考项目

- **[HarukaBot](https://github.com/SK-415/HarukaBot)** — 动态截图功能的灵感来源
- **[biliup](https://github.com/biliup/biliup)** — B 站扫码登录流程参考
- **[blrec](https://github.com/acgnhiki/blrec)** — 直播监控、弹幕 WebSocket、WBI 签名参考
- **[RSSHub](https://github.com/DIYgod/RSSHub)** — 动态 API 请求参数与 dm 校验、WBI 实现参考
- **[douyin-downloader](https://github.com/jiji262/douyin-downloader)** — 抖音链接解析与单视频下载链路移植来源
- **[f2](https://github.com/Johnserf-Seed/f2)** — 抖音 ABogus / msToken 相关实现
- **[Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)** — 抖音 XBogus 签名实现
- **[douyin_parse](https://github.com/DLWangSan/douyin_parse)** — 抖音扫码登录（Playwright）流程参考
- **[webrcon](https://github.com/Facepunch/webrcon)** — Rust RCON WebSocket 协议参考

---

<p align="center">
<sub>Made with ❤️ by <a href="https://github.com/cyxc1124">cyxc1124</a></sub>
</p>
