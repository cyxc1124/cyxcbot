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

功能改动从功能分支开 PR / MR 合进 `develop`，不要直接推 `develop` 或 `main`，下述 GitLab 同步例外除外。GitHub PR 合并后先同步两端 `develop`，再清理功能分支。

**GitLab 同步例外**：可以将 GitHub `develop` 的已合并结果快进推送到 GitLab `develop`，无需另开 GitLab MR。同步前先获取 GitHub 最新 `develop`，确认 GitLab `develop` 是其祖先，再通过明确的 GitLab URL 推送，避免误推 GitHub：

```bash
git push https://gitlab.cyxc.club/cyxc1124/cyxcbot.git refs/remotes/origin/develop:refs/heads/develop
```

若两端存在分叉或无法快进，停下来询问用户，不强推覆盖 GitLab 独有提交。

### 版本与镜像

发版时从 `develop` 开 PR / MR 到 `main`，**合并后再打 annotated tag**（如 `v2.11.8`），并 `git push origin v2.11.8`。不要在 `develop` 上直接打发行 tag。只改 CI 不用打 tag；运行时依赖或业务改动才打。

`v*` tag 会触发 GitHub 推送 GHCR 镜像与 Windows 包（GitHub Release），以及 GitLab 推送 Registry 镜像。`origin` 配置为同时 push GitHub 与 GitLab 时，推一次 tag 两边都会收到。

发版变更必须同步两份 Helm chart 的 `appVersion` / `image.tag`，与发行 tag 使用同一版本号：

| Chart | 路径（相对仓库根目录） | 镜像 repository |
|-------|------------------------|-----------------|
| 仓内公开默认 | `deploy/helm` | 保持 GHCR 默认值 |
| 仓外现网 | `../helm-chart/cyxcbot-chart` | `registry.gitlab.cyxc.club/cyxc1124/cyxcbot` |

现网镜像 repository 与 Kaniko 推送的 GitLab Registry 一致，不要改成 GHCR 或 Harbor。模板改动先改仓内 `deploy/helm`，再同步到现网；现网 overlay 含拉取密钥，不要把密钥拷回本仓。

GitLab CI 拉取 Docker Hub 基础镜像走 Harbor 代理，例如 `harbor.cyxc.club/dockerhub/library/python:3.14`、`harbor.cyxc.club/dockerhub/martizih/kaniko:v1.28.3-debug`。
