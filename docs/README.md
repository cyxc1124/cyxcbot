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

```bash
# 使用 SSH 部署（需先配置 GitHub Pages）
USE_SSH=true npm run deploy
```

站点配置见 `docusaurus.config.ts` 中的 `url` 与 `baseUrl`。
