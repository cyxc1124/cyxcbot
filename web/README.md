# cyxcbot Web Admin

React + TypeScript + Tailwind CSS 管理面板，对接后端 `/api/v1` API。

完整文档：[Web Admin 概览](https://cyxc1124.github.io/cyxcbot/docs/web-admin/overview)

## 后端（项目根目录）

API 由 NoneBot / Admin 服务提供，本地请使用项目虚拟环境启动，勿用系统 Python：

```bash
# 在仓库根目录
./.venv/bin/python bot.py
# 或先激活 venv：source .venv/bin/activate，再执行 python bot.py
```

首次开发请先按根目录 [README.md](../README.md) 创建 `.venv` 并安装 `requirements.txt`。

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
| `/dynamic` | B 站动态订阅 |
| `/live` | B 站直播订阅 |
| `/x` | X 推文订阅 |
| `/groups` | 群组（守卫、状态查询、B 站/抖音/X 链接等） |
| `/private` | 好友（同上） |
| `/templates/bilibili` | B 站消息模板 |
| `/templates/x` | X 消息模板 |
| `/templates/douyin` | 抖音消息模板 |
| `/settings/bilibili-monitor` | B 站监控参数（间隔、WebSocket、截图等） |
| `/settings/x-monitor` | X 监控参数 |
| `/settings/account` | B 站账号（扫码登录 / Cookie） |
| `/settings/douyin-account` | 抖音账号 |
| `/settings/x-account` | X 账号与代理 |
| `/settings/bot` | 机器人（超级用户、状态查询白名单） |
| `/logs` | 实时运行日志（WebSocket） |
| `/about` | 版本与构建信息 |

旧路径 `/mappings`、`/settings/monitor`、`/settings/templates`、`/audit`、`/events` 会自动重定向到新位置。
