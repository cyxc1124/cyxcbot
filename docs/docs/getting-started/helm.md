---
sidebar_position: 5
---

# Helm 部署

在 Kubernetes 上通过 Helm Chart 部署机器草，适用于 **2.0+** 版本。

Helm 仅注入启动级环境变量；监控映射、B 站 Cookie、官方 Bot 凭证、权限策略等业务配置均在 **Web Admin** 中管理。默认 `DRIVER=~fastapi+~httpx+~websockets`（`nonebot.driver`）。

## 前置条件

- Kubernetes 1.23+
- Helm 3.x
- 集群可拉取镜像 `ghcr.io/cyxc1124/cyxcbot`

## 快速安装

**方式 A — 引用已有 Secret（推荐）**

```bash
kubectl create secret generic cyxcbot-secret \
  --from-literal=web-secret-key='请替换为足够长的随机字符串'

helm install cyxcbot ./deploy/helm \
  --set secret.name=cyxcbot-secret
```

**方式 B — 由 Chart 创建 Secret（测试用）**

```bash
helm install cyxcbot ./deploy/helm \
  --set secret.value='请替换为足够长的随机字符串'
```

安装完成后访问 Web Admin（默认 **8081**），完成 `/setup` 初始化，再按 [接入说明](../configuration/web-admin-setup) 连接机器人。官方 QQ Bot 的公网 HTTPS `/qq/webhook` 回调应转发到 Service 的 `onebot` 端口（默认 **8080**）。

## 架构概览

```
values.yaml
  ├── ConfigMap  → HOST / PORT / WEB_* / 数据库 URL / 日志级别
  ├── Secret     → WEB_SECRET_KEY
  ├── PVC        → /app/data（SQLite 与持久化数据）
  └── Deployment → cyxcbot 容器（8080 机器人接入 + 8081 Web Admin）
```

## 关键配置

### 服务端口

| 字段 | 说明 |
|------|------|
| `service.onebot.port` | OneBot / 官方 QQ Webhook 端口，默认 `8080` |
| `service.webAdmin.port` | Web Admin 端口，默认 `8081` |
| `service.type` | 默认 `LoadBalancer` |

### 数据持久化

默认启用 PVC，挂载到 `/app/data`，供 SQLite 使用。建议为 Playwright 动态截图预留至少 `512Mi` 内存 request、`2Gi` limit。

### PostgreSQL（可选）

默认依赖仅包含 SQLite 驱动；改用 PostgreSQL 前需在自定义镜像中安装与 URL 匹配的驱动（下例为 `psycopg`），仅修改 URL 不会安装驱动。

```yaml
database:
  url: "postgresql+psycopg://user:password@postgres:5432/cyxcbot"
```

切换 URL 不会迁移已有 SQLite 数据；保留原库备份，并单独安排数据迁移与校验。

## 升级与卸载

升级前备份数据库并保留原 `WEB_SECRET_KEY`，启动时会自动应用迁移。卸载前确认 PVC 中的数据已有备份；由 Chart 创建的 PVC 会随 release 卸载删除，需要独立保留数据时使用 `persistence.existingClaim` 引用预先管理的 PVC。

```bash
helm upgrade cyxcbot ./deploy/helm -f my-values.yaml
helm uninstall cyxcbot
```

完整配置说明见仓库 [`deploy/helm/README.md`](https://github.com/cyxc1124/cyxcbot/blob/main/deploy/helm/README.md)。
