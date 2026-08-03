# 抖音链接解析

自动识别群聊 / 私聊中的抖音分享链接（含 `v.douyin.com` 短链），下载无水印视频并以 QQ 视频消息回传。

## 行为

- 监听 `on_message(priority=4, block=False)`（与 B 站链接解析同级，互不 `block`）
- 策略默认关闭；仅当群 / 好友在 Web Admin「抖音链接」中开启后生效
- 依赖独立的抖音 Cookie（设置 → 抖音账号），不共用 B 站 Cookie
- 文案模板键：`link_template_douyin`（占位符：`{video}` `{title}` `{author}` `{url}` `{aweme_id}`）

## 配置入口

| 位置 | 说明 |
|------|------|
| 群管理 → 抖音链接 | 按群开关 |
| 好友管理 → 抖音链接 | 按好友开关 |
| 设置 → 抖音账号 | Cookie 粘贴保存（扫码登录后续支持） |

## 实现

下载链路见 `utils/douyin_api/`（自 douyin-downloader 单视频路径移植）。
