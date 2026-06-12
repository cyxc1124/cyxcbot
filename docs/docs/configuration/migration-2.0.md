---
sidebar_position: 3
---

# 1.x 迁移指南

如果你从 1.x 升级到 2.0，主要变化是**业务配置从环境变量迁移到 Web Admin + 数据库**。

## 核心变化

| 配置项 | 1.x | 2.0 |
|--------|-----|-----|
| 直播/动态监控映射 | `LIVE_MONITOR_MAPPING` 等环境变量 | Web Admin `/live`、`/dynamic` |
| B 站 Cookie | `BILIBILI_COOKIE` 环境变量 | Web Admin → 设置 → B 站账号 |
| 状态查询权限 | `STATUS_CHECK_ALLOWED_QQ` | Web Admin → 群组/好友策略 |
| 链接解析开关 | 环境变量 | Web Admin → 群组/好友策略 |
| 消息模板 | 硬编码或环境变量 | Web Admin → 消息模板 |
| 部署 | 仅 Docker | Docker + Windows 可执行包 |

## 迁移步骤

1. **备份数据**：导出旧版配置笔记，备份数据库（如有）
2. **设置 `WEB_SECRET_KEY`**：2.0 必填，生成足够长的随机字符串
3. **启动 2.0**：按 [快速开始](../getting-started/quick-start) 部署
4. **完成 `/setup`**：创建管理员账户
5. **在 Web Admin 中重新配置**：
   - 监控映射（对照旧 `*_MAPPING` 环境变量）
   - B 站账号（对照旧 `BILIBILI_COOKIE`）
   - 权限策略与消息模板
6. **删除旧环境变量**：移除 `LIVE_MONITOR_*`、`DYNAMIC_MONITOR_*` 等，避免混淆

## 弃用提示

启动时若检测到旧版业务环境变量，日志中会出现弃用警告。这些变量在 2.0 中不再生效，请尽快迁移到 Web Admin。

## 数据兼容性

2.0 使用新的数据库 schema，通过 `shared/db/migrations` 自动迁移。从 1.x 直接升级时建议：

- 保留 `data/` 目录挂载（SQLite 数据）
- 首次启动后检查 Web Admin 中配置是否完整
- 如有问题，查看 `/logs` 页面或容器日志
