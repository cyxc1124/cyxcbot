---
sidebar_position: 3
---

# Docker Compose 部署

使用 GHCR 预构建镜像，适合单机或 NAS 快速部署。

## 快速开始

```bash
cd deploy/compose

# 首次部署创建 .env，填写唯一、至少 32 字符的随机密钥：
# WEB_SECRET_KEY=<你的随机密钥>
# Compose 从同目录 .env 读取，未设置会失败。

docker compose pull
docker compose up -d
```

首次启动后访问 `http://<主机>:8081`，尽快完成 `/setup` 初始化（未初始化前任何人可抢先创建管理员）。

`WEB_SECRET_KEY` 同时用于登录令牌签名和数据库内凭证加密。请保存此 `.env`，重启或升级时继续使用原值，不要每次重新生成。若已在 shell 中导出同名变量，Compose 优先使用该环境变量。

OneBot 协议端反向 WebSocket 连接 `ws://<宿主机>:8080/onebot/v11/ws`；使用官方 QQ Bot 时，将公网 HTTPS `/qq/webhook` 转发到该端口。接入步骤见 [Web Admin 初始化](../configuration/web-admin-setup)。

## 配置项

直接修改 `docker-compose.yml`：

| 字段 | 说明 |
|------|------|
| `image` | 镜像与版本 tag |
| `ports` | 宿主机端口映射（默认 8080 / 8081） |
| `volumes` | 数据目录（默认 `./data` → `/app/data`，含数据库与 `logs/` 磁盘日志） |
| `environment.WEB_SECRET_KEY` | **必填**，登录令牌签名与凭证加密密钥 |
| `environment.*` | 其他启动级配置，见 [环境变量](../configuration/env-vars) |

业务配置（监控映射、B 站 Cookie 等）在 Web Admin 面板中管理。磁盘日志默认写入 `./data/logs/`，见 [日志配置](../configuration/logging)。

通过 OneBot 发送本地视频文件时，机器人和协议端必须以相同路径访问共享媒体目录，并在面板中设置「链接解析共享媒体目录」；挂载示例见 Compose 文件注释。

## 常用命令

```bash
docker compose logs -f
docker compose down
docker compose pull && docker compose up -d
docker compose ps
```

升级前先备份数据库和 `.env`，将 `image` 改为目标发行 tag 后再拉取并重建。启动时会自动执行数据库迁移。

## 故障排查

**镜像拉取失败** — 若 GHCR 包为私有，先执行 `docker login ghcr.io`

**Web Admin 无法访问** — 检查 `curl http://127.0.0.1:8081/health`

**OneBot 连不上** — 协议端应连接 `ws://<宿主机 IP>:8080/onebot/v11/ws`，检查端口映射和防火墙
