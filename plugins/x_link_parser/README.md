# X 链接解析

自动识别群聊 / 私聊中的 X (Twitter) 链接（`x.com` / `twitter.com` / `t.co`），经 X API 拉取推文并以文字 + 图片 / 视频回传。

## 行为

- 监听 `on_message(priority=4, block=False)`（与 B 站 / 抖音链接解析同级，互不 `block`）
- 策略默认关闭；仅当群 / 好友在 Web Admin「X 链接」中开启后生效
- 复用 X 监控的 Bearer Token 与代理（设置 → X 账号）
- 文案模板键：`link_template_x`（占位符：`{media}` `{name}` `{username}` `{time}` `{text}` `{url}` `{tweet_id}`）
- 图片过多时按批发送（每条最多 10 张），避免 QQ NT `sendMsg result=34`
- 视频 / GIF / 图片：经代理下载到共享媒体目录后以本地 `file://` 交给 OneBot（含视频时与文案拆开发送，同抖音）

## 官方 QQ Bot

- 支持官方群/C2C 原生消息事件，媒体通过 QQ 富媒体接口上传，回复沿用原事件的 `msg_id` 与递增序号；全部发送结束后才清理暂存文件。
- [平台被动回复预算](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/overview.html)为群聊每条消息五次、单聊四次。官方侧合并文案并回传预算内的图片/视频，超出媒体明确提示查看原推文；多链接消息只解析首个，提示其他链接分开发送。OneBot 维持原有批次和多链接行为。
- 超频、权限或内容等正常平台拒绝只记录业务警告，不重复输出异常栈。URL 未配置到平台白名单时，共享发送层会移除 URL 后重试。

## 配置入口

| 位置 | 说明 |
|------|------|
| 群管理 → X 链接 | 按群开关 |
| 好友管理 → X 链接 | 按好友开关 |
| 设置 → X 账号 | Bearer Token / 代理（与 `x_monitor` 共用） |
| 设置 → 机器人 | 共享媒体目录（视频需协议端可读） |
| X → 消息模板 | `link_template_x` |
