---
sidebar_position: 2
---

# Docker 部署

在仓库根目录构建镜像并运行容器。

## 构建与运行

```bash
# 构建镜像（仓库根目录）
docker build -t cyxcbot .

# 运行（按需挂载数据目录与 .env）
docker run -d \
  --name cyxcbot \
  -p 8080:8080 \
  -p 8081:8081 \
  -v ./data:/app/data \
  --env-file .env \
  cyxcbot
```

## 首次配置

1. 复制 `env.example` 为 `.env`，至少设置 `WEB_SECRET_KEY`
2. 启动容器后访问 `http://<主机>:8081`
3. 完成 `/setup` 初始化
4. 协议端连接宿主机 **8080** 端口

镜像由 GitHub Actions 自动构建并推送到 GHCR，也可直接使用预构建镜像，参见 [Docker Compose](./docker-compose)。

## 端口说明

| 端口 | 用途 |
|------|------|
| 8080 | OneBot 协议（反向 WebSocket） |
| 8081 | Web Admin API 与静态前端 |
