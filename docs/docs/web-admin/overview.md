---
sidebar_position: 1
---

# 管理面板概览

Web Admin 是机器草的浏览器管理界面，基于 React + TypeScript + Tailwind CSS 构建，对接后端 `/api/v1` API。

侧栏按概览 / B 站 / X / 抖音 / 会话 / 游戏 / AI 图片检测 / 运行日志 / 系统分组。每个平台集中自己的账号、订阅参数、解析与模板；系统只保留跨平台通用设置，其中网络代理供 X、AI 图片检测等功能分别选用。游戏 → Rust 管理内部按远控与权限、玩家与积分分层；AI 图片检测分为检测来源、视觉模型与触发命令。页面细节见 [页面说明](./pages)。

## 访问地址

- 生产环境：`http://<主机>:8081`
- 本地开发：前端 `http://localhost:5173`，API `http://localhost:8081`

## 技术说明

- 前端源码位于仓库 `web/` 目录
- 生产构建产物 `web/dist/` 由后端 FastAPI 静态文件服务托管
- 实时日志通过 SSE 推送（内存缓冲，不持久化）；磁盘日志见 [日志配置](../configuration/logging)

## 认证

使用 JWT 认证。浏览器登录后，凭据保存在 HttpOnly Cookie 中，并拒绝跨站请求；脚本等 API 客户端仍可使用 `Authorization: Bearer`。

`WEB_SECRET_KEY` 用于签名登录凭据，并加密数据库中的 Cookie、Token 等敏感配置；Web Admin 启动前必须设置（≥32 字符随机串）。未设置时机器人进程仍可运行，但面板不会监听。详见 [环境变量](../configuration/env-vars)。

登录失败次数有限制，超出后需等待窗口过期，规则见 [初始化与机器人接入](../configuration/web-admin-setup)。

首次访问通过 `/setup` 创建管理员；之后通过 `/login` 登录。

登录后，右上角账户菜单显示用户名和角色，并提供「修改密码」和「退出登录」。手机端点击用户图标展开菜单。修改密码时输入当前密码、新密码和确认新密码；新密码至少 8 个字符、最多 72 个 UTF-8 字节，且不能与当前密码相同。修改成功后当前浏览器保持登录，其他旧登录凭据在下一次请求时失效。

更新到包含修改密码功能的版本时，旧版登录凭据会失效，需要重新登录一次；账户和原密码保持不变。

## 与机器人的关系

```
浏览器 ──► Web Admin / FastAPI (8081) ◄──► 数据库
                                           ▲
                                           │
OneBot 协议端 ◄──► NoneBot (8080) ◄──────────┘
                        ▲
                        │ Webhook / 官方 API
                   官方 QQ Bot
```

Web Admin 负责配置管理与状态展示；NoneBot 负责消息收发与监控任务执行。两者共享同一数据库。官方 QQ 回调 `/qq/webhook` 使用机器人端口 8080；接入方法见 [Web Admin 初始化](../configuration/web-admin-setup)。
