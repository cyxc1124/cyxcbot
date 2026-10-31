# cyxcbot Helm Chart

在 Kubernetes 上部署 [机器草 cyxcbot](https://github.com/cyxc1124/cyxcbot) 的 Helm Chart。

适用于 **2.0+** 版本：Helm 仅注入启动级环境变量，监控映射、B 站 Cookie、权限策略等业务配置均在 **Web Admin** 面板中管理。

## 架构

```
values.yaml
  ├── ConfigMap  → HOST / PORT / WEB_* / 数据库 URL / 日志级别
  ├── Secret     → WEB_SECRET_KEY
  ├── PVC        → /app/data（SQLite 与持久化数据）
  └── Deployment → cyxcbot 容器（8080 OneBot / 官方 QQ Webhook + 8081 Web Admin）
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

安装完成后，访问 Web Admin（默认端口 **8081**），完成 `/setup` 初始化，再在面板里配置监控订阅与会话策略。

OneBot 协议端（如 NapCat）需反向 WebSocket 连接 `ws://<Service 地址>:8080/onebot/v11/ws`，地址填写在协议端。

官方 QQ Bot 在 Web Admin → 系统 → 机器人接入中配置 AppID 与 AppSecret。默认使用 Webhook，公网 HTTPS `/qq/webhook` 须经反向代理转发到 Service 的 **8080** 端口，不是管理面板的 **8081**。Chart 仅提供 Service，公网域名、TLS 与 Ingress 需自行配置。

## 升级与卸载

升级前备份数据库及原有 `WEB_SECRET_KEY`，继续引用同一 Secret。更换密钥会使数据库内已有 Cookie、Token 等加密配置无法解密。

```bash
helm upgrade cyxcbot ./deploy/helm -f my-values.yaml
helm uninstall cyxcbot
```

## 配置说明

### 镜像

| 字段 | 说明 |
|------|------|
| `image.repository` | 默认 `ghcr.io/cyxc1124/cyxcbot` |
| `image.tag` | 镜像标签，留空则使用 `v` + `Chart.appVersion` |
| `imagePullSecrets` | 拉取私有镜像时的 Secret 列表 |

### 服务端口

| 字段 | 说明 |
|------|------|
| `service.onebot.port` | OneBot / 官方 QQ Webhook 端口，默认 `8080` |
| `service.webAdmin.port` | Web Admin 端口，默认 `8081` |
| `service.type` | 默认 `LoadBalancer`，可按集群改为 `ClusterIP` / `NodePort` |

### 启动级环境变量

| values 字段 | 环境变量 | 说明 |
|-------------|----------|------|
| `nonebot.host` | `HOST` | 机器人监听地址 |
| `nonebot.port` | `PORT` | OneBot / 官方 QQ Webhook 监听端口 |
| `nonebot.driver` | `DRIVER` | 默认 `~fastapi+~httpx+~websockets`，供官方 Bot API 和旧版 WebSocket 使用 |
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

### 共享媒体目录（可选）

通过 OneBot 发送 B 站 / 抖音链接解析的视频时，文件写入共享目录后以 `file://` 交给协议端读取。分离部署时须让机器草与 OneBot 协议端 / QQ 客户端数据目录 **看到同一路径**。官方 Bot 直接上传媒体，不需要与 OneBot 协议端共享此卷。

留空时默认写入 `data/tmp`。与 LLBot 等共用 QQ 数据持久化时，在 Web Admin 将共享媒体目录设为 `/root/.config/QQ/tmp`，并挂载协议端 QQ 数据卷（常见挂载点 `/root/.config/QQ`）：

```yaml
sharedMedia:
  enabled: true
  mountPath: /root/.config/QQ
  existingClaim: <qq-data-pvc>   # kubectl get pvc；与协议端共用同一 claim
```

| 字段 | 说明 |
|------|------|
| `sharedMedia.enabled` | 是否挂载共享卷，默认 `false` |
| `sharedMedia.mountPath` | 容器内挂载点，默认 `/root/.config/QQ`（QQ 数据根目录） |
| `sharedMedia.existingClaim` | **推荐**：复用协议端 QQ 数据 PVC |
| `sharedMedia.hostPath` | 节点 / NAS 本地路径；填写后优先于 PVC |
| `sharedMedia.accessMode` | 自动建 PVC 时的访问模式，默认 `ReadWriteMany` |
| `sharedMedia.size` | 自动建 PVC 大小，默认 `5Gi` |

Web Admin → 系统 → 高级配置 →「链接解析共享媒体目录」设为 `/root/.config/QQ/tmp`（与 LLBot 共用时）。跨节点共享时需使用支持 `ReadWriteMany` 的存储；`hostPath` 仅适用于共享同一节点路径的部署。

### 资源与健康检查

- `resources`：建议为 Playwright 动态截图预留至少 `512Mi` 内存 request、`2Gi` limit
- `probes`：对 Web Admin `/health` 做存活/就绪探测；仅在 `probes.enabled` 和 `webAdmin.enabled` 均为 `true` 时启用

## 配置示例

```yaml
# my-values.yaml
image:
  tag: "v2.11.8"

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

默认依赖和镜像只安装 SQLite 数据库驱动；镜像中的 `libpq-dev` 不等于 Python PostgreSQL 驱动。使用外部 PostgreSQL 时，需先在自建镜像中通过 `scripts/secure_pip.py` 安装与连接串匹配的驱动（下例为 `psycopg`），并验证迁移和启动，再设置 `database.url`：

```yaml
database:
  url: "postgresql+psycopg://user:password@postgres:5432/cyxcbot"
```

`database.url` 由 ConfigMap 注入，勿将含真实密码的 values 文件提交 Git。仅修改 URL 不会迁移已有 SQLite 数据。确认不需要保留本地日志、缓存等文件后才关闭 PVC（`persistence.enabled: false`）；关闭后 `/app/data` 使用 `emptyDir`，Pod 删除后数据丢失。

## 版本历史

- **0.2.0**：适配 2.0+ Web Admin 架构，移除旧版业务环境变量，增加 Secret / PVC / 双端口 Service
- **0.1.0**：初始版本（1.x 环境变量配置，已废弃）
