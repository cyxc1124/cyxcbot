---
sidebar_position: 1
slug: /intro
---

# 介绍

**机器草（cyxcbot）** 是基于 [NoneBot2](https://nonebot.dev/) 的 QQ 机器人，专注 B 站动态、直播监控与群消息推送。内置 **Web Admin** 管理面板，可在浏览器中完成监控配置、权限策略与消息模板管理，无需反复改环境变量。

## 项目由来

机器草最初只是给我自己看的主播 **嘉穗Miho** 做的 QQ 群消息推送工具——把 B 站开播、动态更新及时推到群里，方便粉丝第一时间知道。

后来 **Dreadload** 说他用的机器人不好用了，我就给他安利了机器草。为了让更多人也能方便地用起来，从 **2.0.0** 起做了一次大改版：

| | 1.x（2.0.0 之前） | 2.0.0 及以后 |
|---|---|---|
| 部署方式 | 仅容器（Docker） | 容器 + **Windows 可执行包** |
| 业务配置 | 大量依赖环境变量 | **Web Admin + 数据库** |
| 管理界面 | 无 | React 管理面板 |

如果你还在用 `DYNAMIC_MONITOR_*`、`LIVE_MONITOR_*`、`STATUS_CHECK_*` 等旧环境变量，启动时会有弃用提示——请改到 Web Admin 里配置。详见 [1.x 迁移指南](./configuration/migration-2.0)。

## 功能概览

### B 站监控

- **直播监控**（`live_monitor`）：WebSocket 弹幕 + API 轮询双重机制，开播/下播秒级推送
- **动态监控**（`dynamic_monitor`）：轮询 UP 主动态，可选 Playwright 网页截图
- **视频投稿监控**（`video_monitor`）：监控 UP 主新投稿

### 消息与解析

- **链接解析**（`bilibili_link_parser`）：群内/好友 B 站链接自动解析
- **动态图片提取**：`#提取` / `#获取` 命令，按动态 ID 拉取图片
- **消息模板**：开播、下播、动态等推送文案可在面板自定义

### 权限与安全

- **群消息守卫**（`group_guard`）、**私聊守卫**（`private_guard`）
- **状态查询**（`status_check`）：超级用户或指定 QQ 可查询机器人运行状态

### Web Admin

| 页面 | 说明 |
|------|------|
| `/` | 仪表盘 |
| `/dynamic` | 动态监控配置与运行状态 |
| `/live` | 直播监控配置与运行状态 |
| `/groups`、`/private` | 群组 / 好友管理与策略 |
| `/templates` | 消息模板 |
| `/settings` | 监控参数、B 站账号、机器人设置 |
| `/logs` | 实时运行日志 |
| `/about` | 版本与构建信息 |

## 技术栈

- **机器人**：NoneBot2 + OneBot V11 适配器
- **后端 API**：FastAPI + SQLAlchemy（SQLite / 可选 PostgreSQL）
- **前端**：React + TypeScript + Tailwind CSS
- **截图**：Playwright + Chromium
- **打包**：Docker / PyInstaller（Windows）

## 致谢

- **[嘉穗Miho](https://space.bilibili.com/3493119318297082)** — 机器草最初为她和粉丝群而生
- **Dreadload** — 2.0 改版的直接契机
- **[NoneBot2](https://github.com/nonebot/nonebot2)** — 机器人开发框架
- **[HarukaBot](https://github.com/SK-415/HarukaBot)** — 动态截图功能灵感来源
- **[biliup](https://github.com/biliup/biliup)** — B 站登录功能参考
