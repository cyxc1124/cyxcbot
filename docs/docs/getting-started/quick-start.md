---
sidebar_position: 1
---

# 快速开始

无论选择哪种部署方式，首次启动后的流程相同：

1. 访问 Web Admin（默认 `http://<主机>:8081`）
2. 完成 `/setup` 初始化管理员账户
3. 在面板中配置 OneBot 连接、B 站账号与监控映射
4. 将 OneBot 协议端（如 NapCat）反向 WebSocket 连接到 **8080** 端口

## 部署方式对比

| 方式 | 适用场景 | 文档 |
|------|----------|------|
| Docker | 服务器 / NAS，推荐 | [Docker 部署](./docker) |
| Docker Compose | 单机快速部署，使用 GHCR 镜像 | [Docker Compose](./docker-compose) |
| Windows 可执行包 | Windows 桌面，免装 Python | [Windows 部署](./windows) |
| Helm | Kubernetes 集群 | [Helm 部署](./helm) |
| 本地开发 | 贡献代码、调试功能 | [本地开发](./local-dev) |

## 最低要求

- 可访问 B 站 API 的网络环境
- OneBot V11 协议端（如 [NapCat](https://github.com/NapNeko/NapCatQQ)、[LLOneBot](https://github.com/LLOneBot/LLOneBot) 等）
- 启动前设置 `WEB_SECRET_KEY`（见 [环境变量](../configuration/env-vars)）
