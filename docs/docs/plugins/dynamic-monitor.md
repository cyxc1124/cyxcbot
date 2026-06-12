---
sidebar_position: 2
---

# 动态监控

监控 B 站 UP 主动态更新，并在指定群组/好友发送通知。

:::info 2.0 配置方式
UP 主映射、监控间隔、截图开关等在 **Web Admin → 动态监控** 与 **设置** 中配置，不再使用 `DYNAMIC_MONITOR_*` 环境变量。
:::

## 功能特点

- 自动监控指定 UP 主的动态更新
- 支持多 UP 主、多群/好友
- 可配置监控间隔
- 可选 Playwright 网页截图

## 工作原理

1. 调用 B 站 Web API 获取 UP 主动态（`feed/space` 接口）
2. 记录每个 UP 主最后动态 ID，避免重复推送
3. 首次启动只记录基准点，不推送历史动态
4. 过滤直播动态（由直播监控插件负责）
5. 发现新动态时格式化推送到目标群/好友

## 支持的动态类型

| B 站类型 | 说明 |
|----------|------|
| `DYNAMIC_TYPE_WORD` | 纯文字 |
| `DYNAMIC_TYPE_DRAW` | 图文 |
| `DYNAMIC_TYPE_FORWARD` | 转发 |
| `DYNAMIC_TYPE_AV` | 投稿视频 |
| `DYNAMIC_TYPE_ARTICLE` | 专栏 |
| `DYNAMIC_TYPE_MUSIC` | 音频 |

## 动态截图

启用后推送消息中包含动态网页截图：

- 使用 Playwright + Chromium
- 移动端视图优化
- 截图失败时自动降级为纯文字

需在部署时安装 Playwright 浏览器（Docker 镜像已内置）。

## 消息格式

```
小草Miho 发布了新投稿视频

[动态网页截图]

https://t.bilibili.com/1071700825512869927
```

文案可在 **消息模板** 页面自定义。

## 动态图片提取命令

在群聊或私聊中发送：

- `#提取 <动态ID>`
- `#获取 <动态ID>`

可按动态 ID 拉取图片。

## 注意事项

- 监控间隔不建议过短，推荐 30 秒到 5 分钟
- 截图功能需要额外内存，建议容器 limit ≥ 2Gi
- 需网络可访问 B 站 API
