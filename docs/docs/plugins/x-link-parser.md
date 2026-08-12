---
sidebar_position: 5.6
---

# X 链接解析

自动识别群聊 / 私聊中的 X (Twitter) 链接（`x.com` / `twitter.com` / `t.co`），经 X API 拉取推文并以文字 + 图片 / 视频回传。对应插件：`x_link_parser`。

## 触发方式

无需命令。在已开启策略的群或好友会话中，发送含 X 链接的普通消息即可，例如：

- `https://x.com/{user}/status/{id}`
- `https://twitter.com/...`
- `https://t.co/...`（会跟随重定向解析推文 ID）
- `https://x.com/i/status/{id}`

插件以较低优先级监听消息（`priority=4, block=False`），与 [B 站链接解析](./link-parser)、[抖音链接解析](./douyin-link-parser) 同级，互不阻断。

## 回复内容

- 推文正文、作者、时间、原帖链接
- 图片：本地下载后以图片段回传；张数过多时按批发送（每条最多 10 张）
- 视频 / GIF：下载为 mp4 后以视频段回传；**每个视频单独一条**，避免 QQ 同条多 video 只显示第一条

## 配置

默认**关闭**。需在 Web Admin 中按会话开启，并配置 X 账号：

| 位置 | 说明 |
|------|------|
| **群组 → X 链接** | 按群开关 |
| **好友 → X 链接** | 按好友开关 |
| **设置 → X → 账号与代理** | Bearer Token / 代理（与 `x_monitor` 共用） |
| **X → 消息模板** | `link_template_x` |

## 注意事项

- 须配置 Bearer Token；代理与监控共用
- 视频需协议端能读取共享媒体目录（见设置 → 机器人相关说明）
- `{text}` 中可能含推文自带的 `t.co` 短链；模板中的 `{url}` 是机器人拼出的永久原帖链接
