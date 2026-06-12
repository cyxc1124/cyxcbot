# cyxcbot Helm Chart

在 Kubernetes 上部署 [机器草 cyxcbot](https://github.com/cyxc1124/cyxcbot) 的 Helm Chart。

适用于 **2.0+** 版本：Helm 仅注入启动级环境变量，监控映射、B 站 Cookie、权限策略等业务配置均在 **Web Admin** 面板中管理。

## 架构

```
values.yaml
  ├── ConfigMap  → HOST / PORT / WEB_* / 数据库 URL / 日志级别
  ├── Secret     → WEB_SECRET_KEY
  ├── PVC        → /app/data（SQLite 与持久化数据）
  └── Deployment → cyxcbot 容器（8080 OneBot + 8081 Web Admin）
```

## 前置条件

- Kubernetes 1.23+
- Helm 3.x
- 集群可拉取镜像 `ghcr.io/cyxc1124/cyxcbot`（私有仓库需配置 `imagePullSecrets`）

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

安装完成后，访问 Web Admin（默认端口 **8081**），完成 `/setup` 初始化，再在面板里配置 OneBot 与 B 站监控。

OneBot 协议端（如 NapCat）需反向 WebSocket 连接到 Service 的 **8080** 端口。

## 升级与卸载

```bash
helm upgrade cyxcbot ./deploy/helm -f my-values.yaml
helm uninstall cyxcbot
```

## 配置说明

### 镜像

| 字段 | 说明 |
|------|------|
| `image.repository` | 默认 `ghcr.io/cyxc1124/cyxcbot` |
| `image.tag` | 镜像标签，留空则使用 `Chart.appVersion` |
| `imagePullSecrets` | 拉取私有镜像时的 Secret 列表 |

### 服务端口

| 字段 | 说明 |
|------|------|
| `service.onebot.port` | OneBot 协议端口，默认 `8080` |
| `service.webAdmin.port` | Web Admin 端口，默认 `8081` |
| `service.type` | 默认 `LoadBalancer`，可按集群改为 `ClusterIP` / `NodePort` |

### 启动级环境变量

| values 字段 | 环境变量 | 说明 |
|-------------|----------|------|
| `nonebot.host` | `HOST` | OneBot 监听地址 |
| `nonebot.port` | `PORT` | OneBot 监听端口 |
| `nonebot.commandStart` | `COMMAND_START` | 命令前缀 |
| `nonebot.commandSep` | `COMMAND_SEP` | 命令分隔符 |
| `webAdmin.host` | `WEB_HOST` | Web Admin 监听地址 |
| `webAdmin.port` | `WEB_PORT` | Web Admin 监听端口 |
| `webAdmin.enabled` | `WEB_ADMIN_ENABLED` | 是否启用 Web Admin |
| `database.url` | `SQLALCHEMY_DATABASE_URL` | 数据库连接串 |
| `logging.level` | `LOG_LEVEL` | 日志级别 |

### 密钥（必填，二选一）

| 字段 | 方式 A（引用已有） | 方式 B（Chart 创建） |
|------|-------------------|---------------------|
| `secret.name` | 填写 Secret 名称 | 留空 |
| `secret.key` | Secret 内的 key 名，默认 `web-secret-key` | 同上 |
| `secret.value` | 不填 | 填写密钥值（勿提交 Git） |

方式 B 下 Chart 会自动创建名为 `<release>-secret` 的 Secret。

### 数据持久化

默认启用 PVC，挂载到容器 `/app/data`，供 SQLite 数据库（`sqlite+aiosqlite:///data/cyxcbot.db`）使用。

| 字段 | 说明 |
|------|------|
| `persistence.enabled` | 是否启用 PVC |
| `persistence.size` | 存储大小，默认 `1Gi` |
| `persistence.storageClass` | StorageClass，留空使用集群默认 |
| `persistence.existingClaim` | 复用已有 PVC 名称 |

### 资源与健康检查

- `resources`：建议为 Playwright 动态截图预留至少 `512Mi` 内存 request、`2Gi` limit
- `probes`：对 Web Admin `/health` 做存活/就绪探测

## 配置示例

```yaml
# my-values.yaml
image:
  tag: "v2.1.0"

secret:
  name: cyxcbot-secret

service:
  type: ClusterIP

persistence:
  enabled: true
  size: 2Gi

resources:
  limits:
    memory: 2048Mi
  requests:
    memory: 512Mi

logging:
  level: INFO
```

```bash
helm install cyxcbot ./deploy/helm -f my-values.yaml
```

## PostgreSQL（可选）

若使用外部 PostgreSQL，修改 `database.url` 即可：

```yaml
database:
  url: "postgresql+psycopg://user:password@postgres:5432/cyxcbot"
```

此时可关闭 PVC：`persistence.enabled: false`（或保留用于其他本地文件）。

## 版本历史

- **0.2.0**：适配 2.0+ Web Admin 架构，移除旧版业务环境变量，增加 Secret / PVC / 双端口 Service
- **0.1.0**：初始版本（1.x 环境变量配置，已废弃）
