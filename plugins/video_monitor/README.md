# B 站视频查询

在已配置 UP 主映射的群中，响应命令查询 UP 主最新投稿视频（**非**自动推送监控；新投稿视频通知由动态监控的 `DYNAMIC_TYPE_AV` 类型推送负责）。

> **2.0 配置**：与动态监控共用 UP 主 → 群映射（Web Admin → **动态监控**）。B 站账号在 **设置 → B 站账号** 中配置。
>
> 完整文档：[视频查询](https://cyxc1124.github.io/cyxcbot/docs/plugins/video-monitor)

## 命令

在已配置 UP 主映射的群中发送（支持 `@机器人` 或 `/` 前缀）：

| 命令 | 说明 |
|------|------|
| `最新视频` | 查询该群配置 UP 主的最新投稿 |
| `最新投稿` | 同上 |

## 文件结构

```
plugins/video_monitor/
├── __init__.py   # 命令处理
├── config.py     # 与动态监控共用映射
├── sender.py     # 消息构建与发送
└── README.md
```
