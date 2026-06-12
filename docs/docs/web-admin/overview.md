---
sidebar_position: 1
---

# 管理面板概览

Web Admin 是机器草的浏览器管理界面，基于 React + TypeScript + Tailwind CSS 构建，对接后端 `/api/v1` API。

## 访问地址

- 生产环境：`http://<主机>:8081`
- 本地开发：前端 `http://localhost:5173`，API `http://localhost:8081`

## 技术说明

- 前端源码位于仓库 `web/` 目录
- 生产构建产物 `web/dist/` 由后端 FastAPI 静态文件服务托管
- 实时日志通过 WebSocket 推送

## 认证

使用 JWT 认证。`WEB_SECRET_KEY` 用于签名 Token 和加密 Cookie，**必须在部署前设置**。

首次访问通过 `/setup` 创建管理员；之后通过 `/login` 登录。

## 与机器人的关系

```
浏览器 ──► Web Admin (8081) ──► FastAPI ──► 数据库
                                              │
OneBot 协议端 ──► NoneBot (8080) ◄────────────┘
```

Web Admin 负责配置管理与状态展示；NoneBot 负责消息收发与监控任务执行。两者共享同一数据库。
