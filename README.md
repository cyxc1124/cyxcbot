# 机器草

基于 [NoneBot2](https://nonebot.dev/) 的 QQ 机器人，专注 B 站动态、直播监控与群消息推送。内置 Web Admin 管理面板，可在浏览器中完成监控配置、权限策略与消息模板管理，无需反复改环境变量。

---

## 项目由来

机器草最初只是给我自己看的主播 **嘉穗Miho** 做的 QQ 群消息推送工具——把 B 站开播、动态更新及时推到群里，方便粉丝第一时间知道。

后来 **Dreadload** 说他用的机器人不好用了，我就给他安利了机器草。为了让更多人也能方便地用起来，从 **2.0.0** 起做了一次大改版：

| | 1.x（2.0.0 之前） | 2.0.0 及以后 |
|---|---|---|
| 部署方式 | 仅容器（Docker） | 容器 + **Windows 可执行包** |
| 业务配置 | 大量依赖环境变量（监控映射、Cookie、权限等） | **Web Admin + 数据库**，环境变量只保留启动级项 |
| 管理界面 | 无 | React 管理面板（监控、群组、模板、日志等） |

如果你还在用 `DYNAMIC_MONITOR_*`、`LIVE_MONITOR_*`、`STATUS_CHECK_*` 等旧环境变量，启动时会有弃用提示——请改到 Web Admin 里配置。

---

## 功能概览

### B 站监控

- **直播监控**（`live_monitor`）：WebSocket 弹幕 + API 轮询双重机制，开播/下播秒级推送，支持多房间、多群/好友、@全体
- **动态监控**（`dynamic_monitor`）：轮询 UP 主动态，可选 Playwright 网页截图，支持分散/批量检查模式
- **视频投稿监控**（`video_monitor`）：监控 UP 主新投稿

### 消息与解析

- **链接解析**（`bilibili_link_parser`）：群内/好友 B 站链接自动解析（视频、直播、小程序等），按群/好友单独开关
- **动态图片提取**：`#提取` / `#获取` 命令，按动态 ID 拉取图片
- **消息模板**：开播、下播、动态等推送文案可在面板自定义

### 权限与安全

- **群消息守卫**（`group_guard`）、**私聊守卫**（`private_guard`）：群/好友消息响应总开关
- **状态查询**（`status_check`）：超级用户或指定 QQ 可查询机器人运行状态

### Web Admin

| 页面 | 说明 |
|------|------|
| `/` | 仪表盘 |
| `/dynamic` | 动态监控配置与运行状态 |
| `/live` | 直播监控配置与运行状态 |
| `/groups`、`/private` | 群组 / 好友管理与链接解析、状态查询策略 |
| `/templates` | 消息模板 |
| `/settings` | 监控参数、B 站账号、机器人设置 |
| `/logs` | 实时运行日志（WebSocket） |
| `/about` | 版本与构建信息 |

前端开发说明见 [web/README.md](web/README.md)。各插件细节见 `plugins/*/README.md`。

---

## 技术栈

- **机器人**：NoneBot2 + OneBot V11 适配器
- **后端 API**：FastAPI + SQLAlchemy（SQLite / 可选 PostgreSQL（没测过））
- **前端**：React + TypeScript + Tailwind CSS
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

1. 复制 `env.example` 为 `.env`，至少设置 `WEB_SECRET_KEY`
2. 运行 `cyxcbot.exe`
3. 浏览器打开 `http://localhost:8081` 完成初始化

本地自行打包：

```powershell
.\scripts\build-windows.ps1 -Version "dev"
```

CI 流程见 [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml)。

### 方式三：本地开发

本地开发请使用仓库根目录下的 `venv/`，不要使用系统全局 Python。

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 安装依赖
./venv/bin/pip install -r requirements.txt

# 3. Playwright 浏览器（动态截图需要，安装一次即可）
./venv/bin/playwright install chromium

# 4. 配置环境
cp env.example .env
# 编辑 .env：WEB_SECRET_KEY、SQLALCHEMY_DATABASE_URL 等

# 5. 启动机器人（首次启动自动建表 / 迁移）
./venv/bin/python bot.py

# 6. 另开终端启动前端开发服务器
cd web && npm install && npm run dev
```

Windows（PowerShell）创建 venv：`py -3.11 -m venv venv`，激活：`.\venv\Scripts\Activate.ps1`。

---

## 环境变量

2.0 之后，**只有启动级配置**仍通过环境变量；业务配置（监控映射、B 站 Cookie、权限、模板等）全部在 Web Admin / 数据库中管理。

| 类别 | 变量 | 说明 |
|------|------|------|
| OneBot | `HOST`、`PORT` | 机器人监听地址与端口（默认 `0.0.0.0:8080`） |
| Web Admin | `WEB_HOST`、`WEB_PORT`、`WEB_ADMIN_ENABLED` | API 监听（默认 `8081`） |
| 安全 | `WEB_SECRET_KEY` | JWT 签名密钥（**必填**） |
| 数据库 | `SQLALCHEMY_DATABASE_URL` | 默认 SQLite `sqlite+aiosqlite:///data/cyxcbot.db` |
| 日志 | `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` 等 |

完整示例见 [`env.example`](env.example)。

---

## 项目结构

```
cyxcbot/
├── bot.py                 # 机器人主入口
├── admin/                 # Web Admin API（FastAPI）
├── shared/                # 共享 DB、配置、B 站工具
├── plugins/               # NoneBot 插件
│   ├── live_monitor/      # 直播监控
│   ├── dynamic_monitor/   # 动态监控
│   ├── video_monitor/     # 投稿监控
│   ├── bilibili_link_parser/
│   ├── status_check/
│   ├── group_guard/
│   └── private_guard/
├── web/                   # 管理面板前端
├── utils/                 # B 站 API、截图等工具
├── scripts/               # Windows 打包脚本
├── Dockerfile
├── env.example
└── requirements.txt
```

---

## 开发与测试

```bash
# 代码格式化 / 检查
./venv/bin/ruff check .
./venv/bin/ruff format .

# 单元测试
./venv/bin/pytest
```

---

## 致谢

- **[嘉穗Miho](https://space.bilibili.com/3493119318297082)** — 机器草最初为她和粉丝群而生
- **Dreadload** — 2.0 改版的直接契机；感谢他的反馈与试用
- **[NoneBot2](https://github.com/nonebot/nonebot2)** — 机器人开发框架
- **[HarukaBot](https://github.com/SK-415/HarukaBot)** — 动态截图功能的灵感来源
- **[biliup](https://github.com/biliup/biliup)** — B 站登录功能实现参考
- **[Cursor](https://cursor.com/)** — 本项目大量功能与重构在 Cursor AI 辅助下完成

---

<p align="center">
<sub>Made with ❤️ by <a href="https://github.com/cyxc1124">cyxc1124</a></sub>
</p>
