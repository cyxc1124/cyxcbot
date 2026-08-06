# cyxcbot Docker Compose

使用 GHCR 预构建镜像，在单机 / NAS 上快速部署 [机器草 cyxcbot](https://github.com/cyxc1124/cyxcbot)。

业务配置（监控、B 站 Cookie 等）在 Web Admin 面板中管理；启动前必须设置足够长的随机 `WEB_SECRET_KEY`（Compose 未设置会直接失败）。

## 快速开始

```bash
cd deploy/compose

# 在同目录 .env 或当前 shell 中设置（勿提交真实密钥）
export WEB_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"

docker compose pull
docker compose up -d
```

首次启动后访问 `http://<主机>:8081`，尽快完成 `/setup` 初始化（未初始化时任何人可抢先创建管理员）。

OneBot 协议端（如 NapCat）反向 WebSocket 连接 **8080** 端口。

## 配置

直接修改 `docker-compose.yml`：

| 字段 | 说明 |
|------|------|
| `image` | 镜像与版本 tag |
| `ports` | 宿主机端口映射（默认 8080 / 8081） |
| `volumes` | 数据目录（默认 `./data` → `/app/data`）；可选再挂 NAS 共享媒体目录 |
| `environment.WEB_SECRET_KEY` | **必填**，由 `${WEB_SECRET_KEY}` 注入；JWT 签名与 Cookie 加密密钥 |
| `environment.*` | 其他启动级配置，见根目录 [`env.example`](../../env.example) |

### 与协议端共享媒体目录

B 站「发送视频」会把文件写到共享目录，协议端用 `file://` 直接读取（不再 base64）。分离部署时请让两侧挂到**同一路径**（常见为 QQ 客户端数据目录）：

```yaml
volumes:
  - ./data:/app/data
  - /path/to/shared/QQ:/root/.config/QQ
```

Linux / Docker 默认目录为 `/root/.config/QQ`；Windows 本机默认 `data/tmp`（已落在 `./data` 卷内）。可在 Web Admin → 设置 → 机器人 中修改。K8s 部署见 Helm README 的 `sharedMedia`。

## 常用命令

```bash
docker compose logs -f
docker compose down
docker compose pull && docker compose up -d
docker compose ps
```

## 故障排查

**镜像拉取失败** — 若 GHCR 包为私有，先执行 `docker login ghcr.io`

**Web Admin 无法访问** — `curl http://127.0.0.1:8081/health`

**OneBot 连不上** — 协议端连接宿主机 IP 的 8080 端口
