---
sidebar_position: 2
---

# Docker 部署

在仓库根目录构建镜像并运行容器。

## 构建与运行

先在仓库根目录复制 `env.example` 为 `.env`，填入唯一、至少 32 字符的随机 `WEB_SECRET_KEY`。此密钥用于登录令牌签名和凭证加密，重启和升级时保留原值。

```bash
# 构建镜像（仓库根目录）
docker build -t cyxcbot .

# 运行（持久化数据，通过 .env 注入启动配置）
docker run -d \
  --name cyxcbot \
  -p 8080:8080 \
  -p 8081:8081 \
  -v ./data:/app/data \
  --env-file .env \
  cyxcbot
```

## 首次配置

1. 启动容器后访问 `http://<主机>:8081`，完成 `/setup` 初始化
2. 按 [Web Admin 初始化](../configuration/web-admin-setup) 接入 OneBot 或官方 QQ Bot，再配置监控与会话策略

GitHub Actions 在 `main`、`develop` 和 `v*` tag 推送时构建并推送 GHCR 镜像；PR 执行检查，不推镜像。也可直接使用预构建镜像，参见 [Docker Compose](./docker-compose)。当前 CI 产物为 `linux/amd64`，其他架构需自行构建验证。

## 端口说明

| 端口 | 用途 |
|------|------|
| 8080 | OneBot 反向 WebSocket；官方 QQ Bot 的 `/qq/webhook` 回调 |
| 8081 | Web Admin API 与静态前端 |

升级前备份挂载的 `data/` 和 `.env`；启动新版本时会自动应用数据库迁移。
