---
sidebar_position: 6
---

# 本地开发

本地开发请使用仓库根目录下的 `venv/`，不要使用系统全局 Python。

## 环境准备

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
```

Windows（PowerShell）创建 venv：`py -3.11 -m venv venv`，激活：`.\venv\Scripts\Activate.ps1`。

## 启动服务

```bash
# 启动机器人（首次启动自动建表 / 迁移）
./venv/bin/python bot.py

# 另开终端启动前端开发服务器
cd web && npm install && npm run dev
```

- 机器人 API：`http://localhost:8081`
- 前端开发服务器：`http://localhost:5173`（Vite 代理 API 到 8081）

## 代码检查与测试

```bash
./venv/bin/ruff check .
./venv/bin/ruff format .
./venv/bin/pytest
```

前端构建：`cd web && npm run build`，产物输出至 `web/dist/`，由后端静态文件服务托管。

更多细节见 [开发指南](../development/project-structure)。
