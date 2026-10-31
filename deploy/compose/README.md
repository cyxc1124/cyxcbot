# cyxcbot Docker Compose

使用 GHCR 预构建镜像，在单机 / NAS 上快速部署 [机器草 cyxcbot](https://github.com/cyxc1124/cyxcbot)。

业务配置（监控、B 站 Cookie、官方 Bot 凭证等）在 Web Admin 面板中管理；启动前必须设置足够长的随机 `WEB_SECRET_KEY`（Compose 未设置会直接失败）。官方 Bot 默认使用 Webhook：公网 HTTPS `/qq/webhook` 须转发到机器人端口 8080，而非管理面板 8081。`DRIVER` 默认带 `httpx`+`websockets`，用于官方 API 并兼容旧版 WebSocket。

## 快速开始

```bash
cd deploy/compose

# 仅首次安装生成；将同一值保存到本目录 .env（WEB_SECRET_KEY=生成的值）
# 后续重建与升级直接使用已保存的值，勿重新生成或提交真实密钥
export WEB_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"

docker compose pull
docker compose up -d
```

首次启动后访问 `http://<主机>:8081`，尽快完成 `/setup` 初始化（未初始化时任何人可抢先创建管理员）。

OneBot 协议端（如 NapCat）反向 WebSocket 连接 `ws://<机器草主机>:8080/onebot/v11/ws`；此地址填写在协议端。官方 Bot 凭证在 Web Admin → 系统 → 机器人接入中保存。

升级前备份 `data/` 与 `.env`。`WEB_SECRET_KEY` 用于登录签名和数据库内敏感配置加密；更换密钥会使已有 Cookie、Token 等加密配置无法解密。

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

通过 OneBot 发送 B 站 / 抖音链接解析的视频时，文件会写到共享目录，协议端用 `file://` 直接读取。分离部署时请让两侧挂到**同一路径**（常见为 QQ 客户端数据目录）：

```yaml
volumes:
  - ./data:/app/data
  - /path/to/shared/QQ:/root/.config/QQ
```

默认 `data/tmp`。与 LLBot 共用 QQ 数据持久化时，在 Web Admin → 系统 → 高级配置中设为 `/root/.config/QQ/tmp`（卷挂 QQ 数据根）。官方 Bot 直接上传媒体，不需要与 OneBot 协议端共享此卷。K8s 见 Helm README 的 `sharedMedia`。

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

**OneBot 连不上** — 检查协议端的反向 WebSocket 地址是否为 `ws://<机器草主机>:8080/onebot/v11/ws`

**官方 Bot 收不到事件** — 检查公网 HTTPS `/qq/webhook` 是否转发到 **8080**，以及 Web Admin 中是否保存了对应 AppID 和 AppSecret
