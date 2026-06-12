---
sidebar_position: 1
---

# 项目结构

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
├── web/                   # 管理面板前端（React + Vite）
├── docs/                  # 文档站（Docusaurus）
├── utils/                 # B 站 API、截图等工具
├── deploy/                # Docker Compose / Helm
├── scripts/               # Windows 打包脚本
├── tests/                 # 单元测试
├── Dockerfile
├── env.example
└── requirements.txt
```

## 主要模块

### `admin/`

FastAPI 应用，提供 Web Admin REST API 与 WebSocket 日志推送。启动逻辑在 `admin/startup.py`。

### `shared/`

跨插件共享代码：

- `shared/db/` — SQLAlchemy 模型与 Alembic 迁移
- `shared/config/` — 配置服务与策略
- `shared/bilibili/` — B 站登录等
- `shared/monitor/` — 监控调度公共逻辑

### `plugins/`

NoneBot2 插件，每个插件一个目录，包含 `__init__.py` 入口。插件通过 `pyproject.toml` / NoneBot 插件加载机制自动发现。

### `web/`

React 管理面板，开发时用 Vite 代理 API，生产构建后由后端托管 `web/dist/`。

### `docs/`

Docusaurus 文档站，独立 Node.js 项目。

## 数据流

```
Web Admin (React) ──HTTP/WS──► admin/ (FastAPI) ──► shared/db
                                                      │
NoneBot plugins ◄─────────────────────────────────────┘
        │
        ▼
   OneBot 协议端 ──► QQ
```
