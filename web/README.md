# cyxcbot Web Admin

React + TypeScript + Tailwind CSS 管理面板，对接后端 `/api/v1` API。

## 后端（项目根目录）

API 由 NoneBot / Admin 服务提供，本地请使用项目虚拟环境启动，勿用系统 Python：

```bash
# 在仓库根目录
./venv/bin/python bot.py
# 或先激活 venv：source venv/bin/activate，再执行 python bot.py
```

首次开发请先按根目录 [README.md](../README.md) 创建 `venv` 并安装 `requirements.txt`。

## 开发

```bash
cd web
npm install
npm run dev
```

或从仓库根目录：`cd web && npm run dev`

开发服务器默认运行在 http://localhost:5173，API 请求通过 Vite 代理转发到 `http://localhost:8081`。

## 构建

```bash
npm run build
```

产物输出至 `web/dist/`，由后端静态文件服务托管。

## 页面路由

| 路径 | 说明 |
|------|------|
| `/setup` | 首次初始化管理员账户 |
| `/login` | 登录 |
| `/` | 仪表盘 |
| `/dynamic` | 动态监控（运行状态 + 映射 CRUD） |
| `/live` | 直播监控（运行状态 + 映射 CRUD） |
| `/settings` | 系统设置 |
| `/audit` | 审计日志 |
| `/events` | 系统事件 |
