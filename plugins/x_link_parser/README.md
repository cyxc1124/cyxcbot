# X 链接解析

自动识别群聊 / 私聊中的 X (Twitter) 链接（`x.com` / `twitter.com` / `t.co`），经 X API 拉取推文并以文字 + 图片 / 视频回传。

## 行为

- 监听 `on_message(priority=4, block=False)`（与 B 站 / 抖音链接解析同级，互不 `block`）
- 策略默认关闭；仅当群 / 好友在 Web Admin「X 链接」中开启后生效
- 复用 X 监控的 Bearer Token 与代理（设置 → X 账号）
- 文案模板键：`link_template_x`（占位符：`{media}` `{name}` `{username}` `{time}` `{text}` `{url}` `{tweet_id}`）
- 图片过多时按批发送（每条最多 10 张），避免 QQ NT `sendMsg result=34`
- 视频 / GIF / 图片：经代理下载到共享媒体目录后以本地 `file://` 交给 OneBot（含视频时与文案拆开发送，同抖音）

## 配置入口

| 位置 | 说明 |
|------|------|
| 群管理 → X 链接 | 按群开关 |
| 好友管理 → X 链接 | 按好友开关 |
| 设置 → X 账号 | Bearer Token / 代理（与 `x_monitor` 共用） |
| 设置 → 机器人 | 共享媒体目录（视频需协议端可读） |
| 消息模板 → 链接解析 | `link_template_x` |
