---
sidebar_position: 4
---

# Windows 部署

自 **2.0.0** 起提供 Windows 可执行包，无需安装 Python。

## 使用 Release 包

1. 在 [GitHub Releases](https://github.com/cyxc1124/cyxcbot/releases) 下载 `cyxcbot-windows-<version>.zip`
2. 解压后复制 `env.example` 为 `.env`，设置 `WEB_SECRET_KEY`（≥32 字符随机串，可用下方 PowerShell 命令生成）
3. 运行 `cyxcbot.exe`
4. 浏览器打开 `http://localhost:8081` 完成 `/setup` 初始化

无需安装 Python，即可在 PowerShell 生成密钥：

```powershell
$keyBytes = New-Object byte[] 48
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($keyBytes)
[Convert]::ToBase64String($keyBytes)
$rng.Dispose()
```

将输出填入 `.env` 的 `WEB_SECRET_KEY=`。此密钥用于登录令牌签名和凭证加密，升级时连同 `data/` 一起保留。OneBot 或官方 QQ Bot 的接入步骤见 [Web Admin 初始化](../configuration/web-admin-setup)。

## 本地自行打包

需 Python **3.14**、Node.js **26 LTS（26.13.0+，26.x）**。先按 [本地开发](./local-dev) 创建并激活虚拟环境，再在仓库根目录运行：

```powershell
.\scripts\build-windows.ps1 -Version "dev"
```

CI 对 `main` / `develop` 推送与 PR 构建校验，产物保存在 Actions；`v*` tag 构建后还会上传到 GitHub Release。流程见仓库 [`.github/workflows/build-windows.yml`](https://github.com/cyxc1124/cyxcbot/blob/main/.github/workflows/build-windows.yml)。

## 注意事项

- 动态截图功能依赖 Playwright Chromium，Windows 包已内置
- 数据文件默认保存在程序目录下的 `data/` 文件夹
- 跨主机接入时按需放行 8080（OneBot / 官方 QQ Webhook）与 8081（Web Admin）端口；官方回调还需公网 HTTPS 转发
