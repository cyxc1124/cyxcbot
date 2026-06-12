---
sidebar_position: 4
---

# Windows 部署

自 **2.0.0** 起提供 Windows 可执行包，无需安装 Python。

## 使用 Release 包

1. 在 [GitHub Releases](https://github.com/cyxc1124/cyxcbot/releases) 下载 `cyxcbot-windows-<version>.zip`
2. 解压后复制 `env.example` 为 `.env`，至少设置 `WEB_SECRET_KEY`
3. 运行 `cyxcbot.exe`
4. 浏览器打开 `http://localhost:8081` 完成 `/setup` 初始化

## 本地自行打包

```powershell
.\scripts\build-windows.ps1 -Version "dev"
```

CI 流程见仓库 [`.github/workflows/build-windows.yml`](https://github.com/cyxc1124/cyxcbot/blob/main/.github/workflows/build-windows.yml)。

## 注意事项

- 动态截图功能依赖 Playwright Chromium，Windows 包已内置
- 数据文件默认保存在程序目录下的 `data/` 文件夹
- 防火墙需放行 8080（OneBot）与 8081（Web Admin）端口
