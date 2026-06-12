# 机器草文档

基于 [Docusaurus](https://docusaurus.io/) 的项目文档站。

## 本地开发

```bash
cd docs
npm install
npm start
```

浏览器打开 http://localhost:3000 预览。

## 构建

```bash
npm run build
npm run serve   # 预览构建产物
```

## 部署到 GitHub Pages

推送到 `main` 分支且 `docs/` 有变更时，GitHub Actions（[`.github/workflows/deploy-docs.yml`](../.github/workflows/deploy-docs.yml)）会自动构建并部署。

线上地址：https://cyxc1124.github.io/cyxcbot/

### 首次启用

在 GitHub 仓库 **Settings → Pages** 中：

1. **Source** 选择 **GitHub Actions**
2. 合并含文档的变更到 `main` 后，等待 workflow 完成即可

也可在 Actions 页手动运行 **Deploy Docs to GitHub Pages**（`workflow_dispatch`）。

### 部署失败排查

若出现 `Branch "main" is not allowed to deploy to github-pages`，说明 `github-pages` 环境的**部署分支限制**未包含 `main`：

1. 打开 **Settings → Environments → github-pages**
2. 在 **Deployment branches** 中添加 `main`（或选择 **No restriction**）

站点路径配置见 `docusaurus.config.ts` 中的 `url` 与 `baseUrl`。
