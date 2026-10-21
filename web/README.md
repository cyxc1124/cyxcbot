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
node ../scripts/secure_npm.cjs install
node ../scripts/secure_npm.cjs run dev
```

或从仓库根目录：`cd web && node ../scripts/secure_npm.cjs run dev`

开发服务器默认运行在 http://localhost:5173，API 请求通过 Vite 代理转发到 `http://localhost:8081`。

## 构建

```bash
node ../scripts/secure_npm.cjs run build
```

产物输出至 `web/dist/`，由后端静态文件服务托管。

本地拉取新代码后，访问后端 8081 的页面仍会使用上次构建的 `web/dist/`，不会自动更新。请在 `web/` 执行 `node ../scripts/secure_npm.cjs run build` 后刷新页面；若后端 Python 代码也有变化，需要重启自己启动的 `bot.py`。开发时可改用 Vite 终端实际显示的地址（默认 5173，端口占用时可能改变），前端源码会自动更新。

## 外观设置

颜色模式使用胶囊式控件，支持白色、黑色和跟随系统；选择会保存在当前浏览器，刷新或登录后继续生效。「跟随系统」会响应系统颜色模式的实时变化。界面统一使用固定的基础配色和系统字体，不再提供配色方案与字体选择；旧的配色和字体偏好会在下次加载时清理，不影响登录状态与颜色模式。

登录、首次初始化与后台使用统一头像、品牌区、卡片、按钮和表单样式，使用浅灰画布、白色侧栏与圆角面板，蓝色强调操作和选中状态，深色模式使用对应语义色值。登录页品牌后展示前端构建版本，后台保留服务端版本和提交链接；未注入构建信息时显示 `dev`。页面底部统一显示版权文字。界面不包含动态背景，并响应系统的减少动态效果设置。

登录后的顶栏在颜色模式左侧显示 OneBot 与官方 Bot 的连接状态，每 30 秒更新，请求超过 10 秒会取消并显示「状态未知」，下次轮询会重试。手机端收为「连接」入口，点击可查看两路状态、连接说明及官方 Bot 设置；横屏或短屏时详情可内部滚动，支持点击外部或按 Escape 关闭。未配置的官方 Bot 显示中性状态；已配置时仅将当前 AppID 的官方 Bot 计为已连接。Webhook 的接入状态依据有效事件识别，不作为长连接在线检测。顶栏使用独立的 `/api/v1/connections/bots` 接口，仅查看 OneBot 本地注册连接，不请求协议端账号信息，也不触发 B 站登录检查。

右上角账户菜单显示用户名和角色，提供「修改密码」与「退出登录」；手机端点击用户图标展开。修改密码须验证当前密码并重复输入新密码，新密码至少 8 个字符且不超过 72 个 UTF-8 字节。成功后当前浏览器更新登录凭据，其他旧凭据在下一次请求时失效。更新到包含此功能的版本后，原有登录需重新登录一次。

Web 登录凭据使用仅限当前主机、`HttpOnly`、`SameSite=Strict` 的 Cookie，作用于 `/api/v1`；前端不读取 JWT，也不将其保存到 localStorage 或 sessionStorage。升级时清理旧的浏览器令牌，需要重新登录一次；刷新页面会通过 Cookie 恢复会话，退出登录会由服务端清除 Cookie。HTTPS 请求及浏览器以 HTTPS 访问的反向代理使用 Secure Cookie；直接 HTTP 访问仍可用，公网部署应使用 HTTPS。API 必须与页面同源访问，Vite 的 `/api` 代理保留原始 Host；Cookie 请求还要求专用请求头并拒绝跨源请求，CORS 不允许携带浏览器凭据。独立 API 客户端仍可通过原有登录/初始化接口获取 JSON 令牌，再使用 `Authorization: Bearer …`，无需使用 Cookie。用于识别会话更新的浏览器标记不包含凭据。

TLS 代理应保留浏览器原始 Host。若代理改写 Host，请设置启动环境变量 `WEB_PUBLIC_ORIGIN=https://bot.example.com`（仅协议、主机及可选端口，不含路径），供缺少 `Sec-Fetch-Site` 的浏览器按公网 Origin 校验。保留 Host、仅在代理终止 HTTPS 的场景可直接识别同一 Host 的 HTTPS 源；不会信任客户端随意提交的 `X-Forwarded-Host`。

功能模式采用原生单选按钮语义的卡片选项，支持 Tab 聚焦和方向键切换：动态图片模式、卡片取色来源、官方 Bot 接入方式、X 代理协议共用同一组件。开启「启用动态图片」后才显示动态图片模式，选择莫奈卡片后再显示取色来源，默认使用作者头像；关闭动态图片会保留已选模式与取色来源，已有的明确取色选择不受默认值变更影响。启用/停用继续使用开关；目标、筛选等数据选择保留原有控件。设置表单统一在内容末尾保存，桌面与手机使用相同入口。

## 功能分组与页面路由

侧栏按 B 站、X、抖音、会话、游戏和系统分组。运行日志为独立入口，位于系统上一行。每个平台集中自己的订阅、链接解析、模板、参数与账号；游戏下的 Rust 管理按远控与权限、玩家与积分分层，各层级均可折叠。系统只保留机器人接入、权限、通用命令和高级配置。进入分组时收起其他分组，当前页面的分组会自动展开。

消息模板按订阅推送、命令回复、链接解析分类；图片提取的四种结果收在该功能下，保留原有编辑、预览、恢复默认、保存和切换草稿确认。链接解析复用群组与好友页的策略组件，不新增配置或权限开关。

| 路径 | 说明 |
|------|------|
| `/setup` | 首次初始化管理员账户 |
| `/login` | 登录 |
| `/` | 仪表盘 |
| `/bilibili/dynamic` | B 站动态订阅 |
| `/bilibili/live` | B 站直播订阅 |
| `/x/subscriptions` | X 推文订阅 |
| `/groups` | 群组（守卫、状态查询、B 站/抖音/X 链接等） |
| `/friends` | 好友（同上） |
| `/bilibili/templates` | B 站消息模板 |
| `/x/templates` | X 消息模板 |
| `/douyin/templates` | 抖音消息模板 |
| `/bilibili/settings` | B 站监控参数（间隔、WebSocket、截图等） |
| `/x/settings` | X 监控参数 |
| `/bilibili/account` | B 站账号（扫码登录 / Cookie） |
| `/douyin/account` | 抖音账号 |
| `/x/account` | X 账号与代理 |
| `/system/permissions` | 全局权限（超级用户、状态查询额外授权） |
| `/system/connections` | 官方 QQ Bot 接入与 OneBot 连接说明 |
| `/system/commands` | 通用命令触发词、开关与前缀 |
| `/system/advanced` | 链接解析共享媒体目录 |
| `/bilibili/parser`、`/x/parser`、`/douyin/parser` | 对应平台的群组 / 好友解析策略 |
| `/rust/remote/servers`、`groups`、`friends`、`commands`、`custom` | Rust 远控与权限下的服务器、会话权限、命令 |
| `/rust/players/accounts`、`/rust/players/shop` | Rust 玩家积分与绑定、积分商城 |
| `/logs` | 实时运行日志（SSE，Cookie 会话鉴权，断线重连） |
| `/about` | 版本与构建信息 |

旧版页面路径不再保留专用重定向。群组、好友页支持 `?tab=status` 等标签直达；平台解析页支持 `?scope=friends`，刷新和浏览器前进后退会保留所选视角。
