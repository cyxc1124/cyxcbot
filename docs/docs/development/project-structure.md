---
sidebar_position: 1
---

# 项目结构

```
cyxcbot/
├── bot.py                 # 机器人主入口
├── admin/                 # Web Admin API（FastAPI）
├── shared/                # 共享 DB、配置、双栈适配、B 站工具
├── plugins/               # NoneBot 插件
│   ├── live_monitor/      # 直播监控
│   ├── dynamic_monitor/   # 动态监控
│   ├── x_monitor/         # X 推文监控
│   ├── video_monitor/     # 视频查询命令
│   ├── bilibili_link_parser/
│   ├── douyin_link_parser/
│   ├── x_link_parser/
│   ├── rust_rcon/         # Rust WebRCON 远控
│   ├── rust_player/       # Rust 群积分 / 签到 / 商城
│   ├── group_special_title/  # 群头衔设置
│   ├── status_check/
│   ├── group_guard/
│   └── private_guard/
├── web/                   # 管理面板前端（React + Vite）
├── docs/                  # 文档站（Docusaurus）
├── utils/                 # B 站 / 抖音 / X / Rust RCON、截图等工具
├── deploy/                # Docker Compose / Helm
├── scripts/               # 依赖安装、浏览器安装、Windows 打包与诊断脚本
├── tests/                 # 单元测试
├── Dockerfile
├── env.example
└── requirements.txt
```

## 主要模块

### `admin/`

FastAPI 应用，提供 Web Admin REST API 与 SSE 日志推送。启动逻辑在 `admin/startup.py`。

监控状态、热重载与群/好友列表查询通过 `admin/services/` 的 bridge 模块调用；其他 Admin 模块不直接导入 `plugins.*`。

### `shared/`

跨插件共享代码：

- `shared/db/` — SQLAlchemy 模型与 Alembic 迁移
- `shared/adapter/` — OneBot / 官方 QQ Bot 双栈（ID、入站、出站、热连接、会话缓存）
- `shared/config/` — 配置服务与策略
- `shared/bilibili/` — B 站扫码登录
- `shared/douyin/` — 抖音扫码登录
- `shared/rust_player/` — Rust 群积分、签到、商城存储
- `shared/monitor/` — 监控调度公共逻辑
- `shared/logging/` — Web 日志广播（`broadcast.py`）与磁盘会话日志（`file_sink.py`）
- `utils/bilibili_api/` — B 站 HTTP API 封装
- `utils/douyin_api/` — 抖音解析与下载链路
- `utils/x_api/` — X API 与媒体获取
- `utils/rust_rcon/` — WebRCON 客户端、`status` / `giveto` 辅助

### `plugins/`

NoneBot2 插件，每个插件一个目录，包含 `__init__.py` 入口，由 `bot.py` 加载。业务配置通过 `shared/config/service.py` 的快照读取，热重载沿用各插件已有回调。

`video_monitor` 只处理最新视频查询命令，新投稿自动推送由 `dynamic_monitor` 负责。`group_guard` / `private_guard` 控制入站消息，不拦截监控主动推送。

### `web/`

React 管理面板，开发时用 Vite 代理 API，生产构建后由后端托管 `web/dist/`。

### `docs/`

Docusaurus 文档站，独立 Node.js 项目。

## 数据流

```
Web Admin (React) ──HTTP/SSE──► admin/ (FastAPI) ──► shared/db
                                                      │
NoneBot plugins ◄─────────────────────────────────────┘
        │
        ▼
   OneBot 协议端 / 官方 QQ Bot ──► QQ
```
