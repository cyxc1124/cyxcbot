---
sidebar_position: 6
---

# 本地开发

本地开发请使用 **Python 3.14** 与仓库根目录下的 `.venv/`，不要使用系统全局 `python3`。

## 环境准备

前端开发与 Windows 本地打包统一使用 Node.js **26 LTS（26.13.0+，26.x）**；使用 nvm 时，在仓库根目录运行 `nvm install`、`nvm use`。安装与构建使用本仓库的 CA 包装器，Playwright 保留官方随包的 Node。

```bash
# 1. 创建虚拟环境
python3.14 -m venv .venv

# 2. 安装依赖
./.venv/bin/python scripts/secure_pip.py install -r requirements.txt

# 3. Playwright 浏览器（动态截图 / 抖音扫码需要，安装一次即可）
./.venv/bin/python scripts/playwright_install.py install chromium

# 4. 配置环境
cp env.example .env
```

在 `.env` 中设置 **`WEB_SECRET_KEY`**（长度 ≥ 32 的随机串，勿用仓库占位值）：

```bash
./.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

将输出写入 `.env` 的 `WEB_SECRET_KEY=`。它同时用于登录令牌签名和凭证加密；重启、升级时保留原值，与数据库一起备份。

未设置或密钥不合规时：`./.venv/bin/python bot.py` **仍可启动**，但 Web Admin **不会监听**（日志中有 `Web Admin 未启动`）。只要机器人、不要面板时，可设 `WEB_ADMIN_ENABLED=false`。

数据库默认使用 SQLite（见 `env.example`）。开发与验证请使用独立的数据库和测试目标；`bot.py` 启动时会自动执行迁移并加载数据库内的监控配置。

Windows（PowerShell）创建 venv：`py -3.14 -m venv .venv`，激活：`.\.venv\Scripts\Activate.ps1`。

Windows 下将后续命令中的 `./.venv/bin/python` 替换为 `.\.venv\Scripts\python.exe`。

## 启动服务

```bash
# 启动机器人（首次启动自动建表 / 迁移）
./.venv/bin/python bot.py

# 另开终端启动前端开发服务器（可选）
cd web && node ../scripts/secure_npm.cjs install && node ../scripts/secure_npm.cjs run dev
```

| 服务 | 地址 |
|------|------|
| NoneBot / 机器人接入 | `http://localhost:8080`（OneBot 反向 WebSocket、官方 QQ Webhook） |
| Web Admin API | `http://localhost:8081` |
| 前端开发服务器 | `http://localhost:5173`（Vite 代理 API 到 8081） |

源码中的 `web/dist/` 不入库。首次开发请打开 Vite 地址完成初始化；若要直接访问 8081 的管理页面，先构建前端。机器人接入步骤见 [Web Admin 初始化](../configuration/web-admin-setup)。

## 代码检查与测试

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
./.venv/bin/pytest
```

实际格式化时只处理本次修改的文件。前端测试使用 `cd web && node ../scripts/secure_npm.cjs test`；构建使用 `cd web && node ../scripts/secure_npm.cjs run build`，产物输出至 `web/dist/`，由后端静态文件服务托管。

### 拉取更新后仍显示旧页面

`git pull` 只更新源码，不会重建 `web/dist/`，也不会让已运行的 Python 进程重新加载模块。若直接访问后端 8081 的管理页面，请先在 `web/` 执行 `node ../scripts/secure_npm.cjs run build`，刷新浏览器；后端代码有变化时还需重启自己启动的 `bot.py`。开发服务器应使用 Vite 终端实际显示的地址，默认端口 5173 若被其他项目占用会变动。

更多细节见 [开发指南](../development/project-structure)。
