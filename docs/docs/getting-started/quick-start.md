---
sidebar_position: 1
---

# 快速开始

先按部署方式配置持久化数据目录和 `WEB_SECRET_KEY`，再启动服务。首次启动后的流程相同：

1. 访问 Web Admin（默认 `http://<主机>:8081`）
2. 完成 `/setup` 初始化管理员账户
3. 选择接入方式，可单独使用或双栈并行：OneBot 协议端（如 NapCat）反向 WebSocket 连接 `ws://<机器人主机>:8080/onebot/v11/ws`；官方 QQ Bot 在 **系统 → 机器人接入** 保存凭证，并将公网 HTTPS `/qq/webhook` 回调转发到 **8080**。详细步骤见 [Web Admin 初始化](../configuration/web-admin-setup)
4. 在面板中配置 B 站账号与监控映射；按需再配置 [X 监控](../plugins/x-monitor)、[抖音链接解析](../plugins/douyin-link-parser)、[Rust 群管](../plugins/rust-rcon) 或 [群头衔](../plugins/group-special-title)

命令和链接解析需要在 **群组 / 好友** 页面启用对应会话的消息响应与功能策略；这些入站策略不控制监控主动推送。Rust 群管、积分商城和群头衔仅支持 OneBot。

## 部署方式对比

| 方式 | 适用场景 | 文档 |
|------|----------|------|
| Docker | 服务器 / NAS，推荐 | [Docker 部署](./docker) |
| Docker Compose | 单机快速部署，使用 GHCR 镜像 | [Docker Compose](./docker-compose) |
| Windows 可执行包 | Windows 桌面，免装 Python | [Windows 部署](./windows) |
| Helm | Kubernetes 集群 | [Helm 部署](./helm) |
| 本地开发 | 贡献代码、调试功能 | [本地开发](./local-dev) |

## 最低要求

- 可访问所用平台 API 的网络环境
- OneBot V11 协议端（如 [NapCat](https://github.com/NapNeko/NapCatQQ)、[LLOneBot](https://github.com/LLOneBot/LLOneBot) 等），或官方 QQ Bot 应用与可用的 Webhook 回调地址
- 使用 Web Admin 时设置 `WEB_SECRET_KEY`（≥32 字符；见 [环境变量](../configuration/env-vars)、[本地开发](./local-dev)）

`WEB_SECRET_KEY` 同时用于登录令牌签名与数据库内凭证加密，重启和升级时应保留原值，并与数据库一起备份。
