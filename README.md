# 机器草

基于 [NoneBot2](https://nonebot.dev/) 的 QQ 机器人，专注 B 站动态、直播监控与群消息推送。内置 Web Admin 管理面板，业务配置在浏览器中完成，环境变量只保留启动级项。

📖 **完整文档**（功能说明、插件与配置）：https://cyxc1124.github.io/cyxcbot/（源码在 [docs/](docs/)，本地预览：`cd docs && npm start`）

---

## 项目由来

机器草最初只是给我自己看的主播 **嘉穗Miho** 做的 QQ 群消息推送工具——把 B 站开播、动态更新及时推到群里，方便粉丝第一时间知道。

后来 **Dreadload** 说他用的机器人不好用了，我就给他安利了机器草。为了让更多人也能方便地用起来，从 **2.0.0** 起做了一次大改版：

| | 1.x（2.0.0 之前） | 2.0.0 及以后 |
|---|---|---|
| 部署方式 | 仅容器（Docker） | 容器 + **Windows 可执行包** |
| 业务配置 | 大量依赖环境变量（监控映射、Cookie、权限等） | **Web Admin + 数据库**，环境变量只保留启动级项 |
| 管理界面 | 无 | React 管理面板（监控、群组、模板、日志等） |

如果你还在用 `DYNAMIC_MONITOR_*`、`LIVE_MONITOR_*`、`STATUS_CHECK_*`、`SUPERUSERS` 等旧环境变量，启动时会有弃用提示——请改到 Web Admin 里配置。

---

## 技术栈

- **机器人**：NoneBot2 + OneBot V11 适配器
- **后端 API**：FastAPI + SQLAlchemy（SQLite，理论上支持 PostgreSQL 但需自行安装驱动）
- **前端**：React + TypeScript + Tailwind CSS + Vite
- **截图**：Playwright + Chromium
- **打包**：Docker / PyInstaller（Windows）

---

## 快速开始

### 方式一：Docker（推荐用于服务器 / NAS）

```bash
# 构建镜像（仓库根目录）
docker build -t cyxcbot .

# 运行（按需挂载数据目录与 .env）
docker run -d \
  --name cyxcbot \
  -p 8080:8080 \
  -p 8081:8081 \
  -v ./data:/app/data \
  --env-file .env \
  cyxcbot
```

镜像由 GitHub Actions 自动构建并推送，详见 [`.github/workflows/build-and-push.yml`](.github/workflows/build-and-push.yml)。

首次启动后访问 `http://<主机>:8081`，完成 `/setup` 初始化管理员账户，再在面板里配置监控与 OneBot 连接。

### 方式二：Windows 可执行包

自 **2.0.0** 起提供 Windows 打包。Release 页下载 `cyxcbot-windows-<version>.zip`，解压后：

1. 复制 `env.example` 为 `.env`，设置 `WEB_SECRET_KEY`（≥32 字符随机串）
2. 运行 `cyxcbot.exe`
3. 浏览器打开 `http://localhost:8081` 完成初始化

本地自行打包：

```powershell
.\scripts\build-windows.ps1 -Version "dev"
```

CI 流程见 [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml)。

### 方式三：本地开发

本地开发请使用 **Python 3.14** 与仓库根目录下的 `.venv/`，不要使用系统全局 `python3`。

```bash
# 1. 创建虚拟环境
python3 -m venv .venv

# 2. 安装依赖
./.venv/bin/pip install -r requirements.txt

# 3. Playwright 浏览器（截图 / 抖音扫码需要，安装一次即可）
./.venv/bin/playwright install chromium

# 4. 配置环境
cp env.example .env
# 生成并写入 WEB_SECRET_KEY（≥32 字符；未设置时机器人可启动，但 Web Admin 不会监听）
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# 5. 启动机器人（请用 venv，不要用系统 python3）
./.venv/bin/python bot.py

# 6. 另开终端启动前端开发服务器（可选）
cd web && npm install && npm run dev
```

Windows（PowerShell）创建 venv：`py -3.14 -m venv .venv`，激活：`.\.venv\Scripts\Activate.ps1`。

- OneBot：`http://localhost:8080`
- Web Admin API：`http://localhost:8081`
- 前端开发服务器：`http://localhost:5173`（Vite 代理 API 到 8081）

更细的说明见文档站 [本地开发](https://cyxc1124.github.io/cyxcbot/getting-started/local-dev)。

---

## 环境变量

2.0 之后，**只有启动级配置**仍通过环境变量；业务配置全部在 Web Admin / 数据库中管理。

| 类别 | 变量 | 说明 |
|------|------|------|
| OneBot | `HOST`、`PORT` | 机器人监听地址与端口（默认 `0.0.0.0:8080`） |
| Web Admin | `WEB_HOST`、`WEB_PORT`、`WEB_ADMIN_ENABLED` | API 监听（默认 `8081`）；`false` 可禁用面板 |
| 安全 | `WEB_SECRET_KEY` | JWT / Cookie 加密密钥（Web Admin 启动时必填，≥32 字符） |
| 数据库 | `SQLALCHEMY_DATABASE_URL` | 默认 SQLite `sqlite+aiosqlite:///data/cyxcbot.db` |
| 日志 | `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` 等 |

完整示例见 [`env.example`](env.example)；明细见 [环境变量](https://cyxc1124.github.io/cyxcbot/configuration/env-vars)。

---

## 项目结构

```
cyxcbot/
├── bot.py                 # 机器人主入口
├── admin/                 # Web Admin API（FastAPI）
├── shared/                # 共享 DB、配置、监控公共逻辑
├── plugins/               # NoneBot 插件
├── web/                   # 管理面板前端
├── docs/                  # 文档站（Docusaurus）
├── utils/                 # B 站 / 抖音 API、截图等工具
├── scripts/               # Windows 打包脚本
├── Dockerfile
├── env.example
└── requirements.txt
```

---

## 开发与测试

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format .
./.venv/bin/pytest
```

---

## 致谢

- **[嘉穗Miho](https://space.bilibili.com/3493119318297082)** — 机器草最初为她和粉丝群而生
- **Dreadload** — 2.0 改版的直接契机；感谢他的反馈与试用
- **[NoneBot2](https://github.com/nonebot/nonebot2)** — 机器人开发框架
- **[Cursor](https://cursor.com/)** — 本项目大量功能与重构在 Cursor AI 辅助下完成

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
