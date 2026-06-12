---
sidebar_position: 5
---

# Helm 部署

在 Kubernetes 上通过 Helm Chart 部署机器草，适用于 **2.0+** 版本。

Helm 仅注入启动级环境变量；监控映射、B 站 Cookie、权限策略等业务配置均在 **Web Admin** 中管理。

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

安装完成后访问 Web Admin（默认 **8081**），完成 `/setup` 初始化。

## 架构概览

```
values.yaml
  ├── ConfigMap  → HOST / PORT / WEB_* / 数据库 URL / 日志级别
  ├── Secret     → WEB_SECRET_KEY
  ├── PVC        → /app/data（SQLite 与持久化数据）
  └── Deployment → cyxcbot 容器（8080 OneBot + 8081 Web Admin）
```

## 关键配置

### 服务端口

| 字段 | 说明 |
|------|------|
| `service.onebot.port` | OneBot 协议端口，默认 `8080` |
| `service.webAdmin.port` | Web Admin 端口，默认 `8081` |
| `service.type` | 默认 `LoadBalancer` |

### 数据持久化

默认启用 PVC，挂载到 `/app/data`，供 SQLite 使用。建议为 Playwright 动态截图预留至少 `512Mi` 内存 request、`2Gi` limit。

### PostgreSQL（可选）

```yaml
database:
  url: "postgresql+psycopg://user:password@postgres:5432/cyxcbot"
```

## 升级与卸载

```bash
helm upgrade cyxcbot ./deploy/helm -f my-values.yaml
helm uninstall cyxcbot
```

完整配置说明见仓库 [`deploy/helm/README.md`](https://github.com/cyxc1124/cyxcbot/blob/main/deploy/helm/README.md)。
