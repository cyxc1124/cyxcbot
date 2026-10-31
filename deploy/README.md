# 部署

| 方式 | 目录 | 说明 |
|------|------|------|
| **Docker Compose** | [`compose/`](compose/) | 单机 / NAS |
| **Helm** | [`helm/`](helm/) | Kubernetes |

## Docker Compose

```bash
cd deploy/compose
export WEB_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"

docker compose pull
docker compose up -d
```

详见 [`compose/README.md`](compose/README.md)。

## Helm

```bash
kubectl create secret generic cyxcbot-secret \
  --from-literal=web-secret-key="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"

helm install cyxcbot ./deploy/helm --set secret.name=cyxcbot-secret
```

详见 [`helm/README.md`](helm/README.md)。

## 维护者发布流程

以下流程在用户授权范围内执行；已有授权无需重复确认。更新 chart 文件不代表执行现网部署。

### 分支与合并

**GitHub 是主仓库**。功能改动从功能分支开 GitHub PR 合进 `develop`，不要直接推 `develop` 或 `main`；PR 合并后再清理对应功能分支。

**GitLab 暂时仅同步发行 tag**，不再同步 `develop`、`main` 或功能分支，也不在 GitLab 创建功能修复 MR。`origin` 的默认推送仅指向 GitHub，保留 `gitlab` 远端用于显式同步发行 tag；不要配置 `origin` 双 push URL，以免普通分支推送同时进入 GitLab。

### 版本与镜像

发版时在 GitHub 从 `develop` 开 PR 到 `main`，**合并后再在 `main` 打 annotated tag**（如 `v2.11.8`）。不要在 `develop` 上直接打发行 tag。只改 CI 不用打 tag；运行时依赖或业务改动才打。

将同一个发行 tag 分别推送到两个远端，使用完整 tag refspec，避免推送代码分支：

```bash
git push origin refs/tags/v2.11.8:refs/tags/v2.11.8
git push gitlab refs/tags/v2.11.8:refs/tags/v2.11.8
```

`v*` tag 会触发 GitHub 推送 GHCR 镜像与 Windows 包（GitHub Release），以及 GitLab 推送 Registry 镜像。两端 tag 应指向同一个 annotated tag 对象；若已有同名 tag 指向不同对象，停止并询问，不强推覆盖。

发版变更必须同步两份 Helm chart 的 `appVersion` / `image.tag`，与发行 tag 使用同一版本号：

| Chart | 路径（相对仓库根目录） | 镜像 repository |
|-------|------------------------|-----------------|
| 仓内公开默认 | `deploy/helm` | 保持 GHCR 默认值 |
| 仓外现网 | `../helm-chart/cyxcbot-chart` | `registry.gitlab.cyxc.club/cyxc1124/cyxcbot` |

现网镜像 repository 与 Kaniko 推送的 GitLab Registry 一致，不要改成 GHCR 或 Harbor。模板改动先改仓内 `deploy/helm`，再同步到现网；现网 overlay 含拉取密钥，不要把密钥拷回本仓。

GitLab CI 拉取 Docker Hub 基础镜像走 Harbor 代理，例如 `harbor.cyxc.club/dockerhub/library/python:3.14`、`harbor.cyxc.club/dockerhub/martizih/kaniko:v1.28.3-debug`。
