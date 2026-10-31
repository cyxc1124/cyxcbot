# 机器草文档

基于 [Docusaurus](https://docusaurus.io/) 的项目文档站。

## 本地开发

需 Node.js **26 LTS（26.13.0+，26.x）**；使用 nvm 时，在仓库根目录运行 `nvm install`、`nvm use`。

```bash
cd docs
node ../scripts/secure_npm.cjs install
node ../scripts/secure_npm.cjs start
```

浏览器打开 http://localhost:3000 预览。

## 构建

以下命令在 `docs/` 目录执行，静态产物输出至 `docs/build/`：

```bash
node ../scripts/secure_npm.cjs run build
node ../scripts/secure_npm.cjs run serve   # 预览构建产物
```

## 部署到 GitHub Pages

- **`main` 推送**：构建并部署到 https://cyxc1124.github.io/cyxcbot/
- **`develop` 推送 / PR**：安装锁定依赖后构建校验，不发布

触发路径：`docs/**`、`.github/workflows/deploy-docs.yml`、`scripts/secure_npm.cjs`、`shared/security/*.cjs`、`shared/security/*.json`。CI 通过包装器执行 `ci` 与 `run build`。Workflow：[`.github/workflows/deploy-docs.yml`](../.github/workflows/deploy-docs.yml)

### 首次启用

在 GitHub 仓库 **Settings → Pages** 中：

1. **Source** 选择 **GitHub Actions**
2. 合并含文档的变更到 `main` 后，等待 workflow 完成即可

也可在 Actions 页手动运行 **Deploy Docs to GitHub Pages**（`workflow_dispatch`）；只有选择 `main` 分支时才会部署，其他分支仅构建。

### 部署失败排查

若出现 `Branch "main" is not allowed to deploy to github-pages`，说明 `github-pages` 环境的**部署分支限制**未包含 `main`：

1. 打开 **Settings → Environments → github-pages**
2. 在 **Deployment branches** 中添加 `main`（或选择 **No restriction**）

站点路径配置见 `docusaurus.config.ts` 中的 `url` 与 `baseUrl`。
