# NoneBot2 机器人项目

基于 NoneBot2 的 QQ 机器人，含 B 站动态/直播监控与 Web Admin 管理面板。

## 开发环境（使用项目内 venv）

本地开发请始终使用仓库根目录下的 `venv/`，不要使用系统全局的 `python` / `pip`。

### 1. 创建虚拟环境

```bash
python3 -m venv venv
```

Windows（PowerShell）：

```powershell
py -3.11 -m venv venv
```

### 2. 激活虚拟环境（可选）

激活后可直接使用 `python` / `pip`；未激活时请使用 `./venv/bin/python` 等显式路径。

macOS / Linux：

```bash
source venv/bin/activate
```

Windows：

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. 安装依赖

```bash
./venv/bin/pip install -r requirements.txt
```

（已激活 venv 时：`pip install -r requirements.txt`）

Playwright 浏览器（动态监控截图需要，安装依赖后执行一次）：

```bash
./venv/bin/playwright install chromium
```

### 4. 配置环境

复制示例配置并按需修改：

```bash
cp env.example .env
```

主要项：`HOST` / `PORT`（OneBot）、`WEB_PORT`（Admin API）、`WEB_SECRET_KEY`、`SQLALCHEMY_DATABASE_URL` 等，详见 `env.example`。

### 5. 启动机器人

首次启动时会**自动初始化数据库**（建表 / 应用迁移），无需单独执行脚本：

```bash
./venv/bin/python bot.py
```

（已激活 venv 时：`python bot.py`）

### 6. 启动 Web 前端开发服务器

```bash
cd web && npm run dev
```

Web Admin 前端说明见 [web/README.md](web/README.md)。

## Docker 部署

容器内使用镜像自带的 Python，与主机 `venv` 无关。构建与运行见 `Dockerfile` 与 `docker-entrypoint.sh`。

## 项目结构

```
cyxcbot/
├── bot.py              # 机器人主入口
├── admin/              # Web Admin API
├── shared/             # 共享 DB / 配置
├── plugins/            # NoneBot 插件
├── web/                # 管理面板前端
├── env.example         # 环境变量示例
├── venv/               # 本地虚拟环境（已 gitignore，需自行创建）
└── requirements.txt
```

<p align="center">
<sub>Made with ❤️ by <a href="https://github.com/cyxc1124">cyxc1124</a></sub><br>
<sub>Developed with ❤️ for Mituantuan Miho Live Stream</sub>
</p>
