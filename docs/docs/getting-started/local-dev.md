---
sidebar_position: 6
---

# 本地开发

本地开发请使用 **Python 3.14** 与仓库根目录下的 `.venv/`，不要使用系统全局 `python3`。

## 环境准备

```bash
# 1. 创建虚拟环境
python3 -m venv .venv

# 2. 安装依赖
./.venv/bin/pip install -r requirements.txt

# 3. Playwright 浏览器（动态截图 / 抖音扫码需要，安装一次即可）
./.venv/bin/playwright install chromium

# 4. 配置环境
cp env.example .env
```

在 `.env` 中设置 **`WEB_SECRET_KEY`**（长度 ≥ 32 的随机串，勿用仓库占位值）：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

将输出写入 `.env` 的 `WEB_SECRET_KEY=`。本地可固定使用同一串，无需每次更换。

未设置或密钥不合规时：`./.venv/bin/python bot.py` **仍可启动**，但 Web Admin **不会监听**（日志中有 `Web Admin 未启动`）。只要机器人、不要面板时，可设 `WEB_ADMIN_ENABLED=false`。

数据库默认使用 SQLite（见 `env.example`），一般无需改动。

Windows（PowerShell）创建 venv：`py -3.14 -m venv .venv`，激活：`.\.venv\Scripts\Activate.ps1`。

## 启动服务

```bash
# 启动机器人（首次启动自动建表 / 迁移）
./.venv/bin/python bot.py

# 另开终端启动前端开发服务器（可选）
cd web && npm install && npm run dev
```

| 服务 | 地址 |
|------|------|
| OneBot | `http://localhost:8080` |
| Web Admin API | `http://localhost:8081` |
| 前端开发服务器 | `http://localhost:5173`（Vite 代理 API 到 8081） |

## 代码检查与测试

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format .
./.venv/bin/pytest
```

前端构建：`cd web && npm run build`，产物输出至 `web/dist/`，由后端静态文件服务托管。

更多细节见 [开发指南](../development/project-structure)。
