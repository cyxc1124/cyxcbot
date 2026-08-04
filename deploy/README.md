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
