---
sidebar_position: 3
---

# Docker Compose 部署

使用 GHCR 预构建镜像，适合单机或 NAS 快速部署。

## 快速开始

```bash
cd deploy/compose

# 编辑 docker-compose.yml，修改 WEB_SECRET_KEY

docker compose pull
docker compose up -d
```

首次启动后访问 `http://<主机>:8081`，完成 `/setup` 初始化。

OneBot 协议端反向 WebSocket 连接 **8080** 端口。

## 配置项

直接修改 `docker-compose.yml`：

| 字段 | 说明 |
|------|------|
| `image` | 镜像与版本 tag |
| `ports` | 宿主机端口映射（默认 8080 / 8081） |
| `volumes` | 数据目录（默认 `./data` → `/app/data`） |
| `environment.WEB_SECRET_KEY` | **必填**，JWT 签名密钥 |
| `environment.*` | 其他启动级配置，见 [环境变量](../configuration/env-vars) |

业务配置（监控映射、B 站 Cookie 等）在 Web Admin 面板中管理。

## 常用命令

```bash
docker compose logs -f
docker compose down
docker compose pull && docker compose up -d
docker compose ps
```

## 故障排查

**镜像拉取失败** — 若 GHCR 包为私有，先执行 `docker login ghcr.io`

**Web Admin 无法访问** — 检查 `curl http://127.0.0.1:8081/health`

**OneBot 连不上** — 协议端应连接宿主机 IP 的 8080 端口
