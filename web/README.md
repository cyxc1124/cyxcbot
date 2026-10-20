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

本地拉取新代码后，访问后端 8081 的页面仍会使用上次构建的 `web/dist/`，不会自动更新。请在 `web/` 执行 `npm run build` 后刷新页面；若后端 Python 代码也有变化，需要重启自己启动的 `bot.py`。开发时可改用 Vite 终端实际显示的地址（默认 5173，端口占用时可能改变），前端源码会自动更新。

## 外观设置

颜色模式使用胶囊式控件，支持白色、黑色和跟随系统；选择会保存在当前浏览器，刷新或登录后继续生效。「跟随系统」会响应系统颜色模式的实时变化。界面统一使用固定的基础配色和系统字体，不再提供配色方案与字体选择；旧的配色和字体偏好会在下次加载时清理，不影响登录状态与颜色模式。

登录、首次初始化与后台使用统一头像、品牌区、卡片、按钮和表单样式，使用浅灰画布、白色侧栏与圆角面板，蓝色强调操作和选中状态，深色模式使用对应语义色值。登录页品牌后展示前端构建版本，后台保留服务端版本和提交链接；未注入构建信息时显示 `dev`。页面底部统一显示版权文字。界面不包含动态背景，并响应系统的减少动态效果设置。

登录后的顶栏在颜色模式左侧显示 OneBot 与官方 Bot 的连接状态，每 30 秒更新，请求超过 10 秒会取消并显示「状态未知」，下次轮询会重试。手机端收为「连接」入口，点击可查看两路状态、连接说明及官方 Bot 设置；横屏或短屏时详情可内部滚动，支持点击外部或按 Escape 关闭。未配置的官方 Bot 显示中性状态；已配置时仅将当前 AppID 的官方 Bot 计为已连接。Webhook 的接入状态依据有效事件识别，不作为长连接在线检测。顶栏使用独立的 `/api/v1/connections/bots` 接口，仅查看 OneBot 本地注册连接，不请求协议端账号信息，也不触发 B 站登录检查。

功能模式采用原生单选按钮语义的卡片选项，支持 Tab 聚焦和方向键切换：动态图片模式、卡片取色来源、官方 Bot 接入方式、X 代理协议共用同一组件。启用/停用继续使用开关；目标、筛选等数据选择保留原有控件。设置页在桌面侧栏提供保存按钮，手机端在表单末尾保存。

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
