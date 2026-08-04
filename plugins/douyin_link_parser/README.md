# 抖音链接解析

自动识别群聊 / 私聊中的抖音分享链接（含 `v.douyin.com` 短链），下载无水印视频并以 QQ 视频消息回传。

## 行为

- 监听 `on_message(priority=4, block=False)`（与 B 站链接解析同级，互不 `block`）
- 策略默认关闭；仅当群 / 好友在 Web Admin「抖音链接」中开启后生效
- Cookie 独立于 B 站（设置 → 抖音账号）；**非硬性必填**，对齐 douyin-downloader：缺省仅 warning，仍尝试游客态；建议配置 `ttwid` / `odin_tt` / `passport_csrf_token`（`msToken` 可缺省自动生成）
- 文案模板键：`link_template_douyin`（占位符：`{video}` `{title}` `{author}` `{url}` `{aweme_id}`）

## 配置入口

| 位置 | 说明 |
|------|------|
| 群管理 → 抖音链接 | 按群开关 |
| 好友管理 → 抖音链接 | 按好友开关 |
| 设置 → 抖音账号 | 扫码登录（Playwright，对齐 douyin_parse）或粘贴 Cookie |

## 实现

下载链路见 `utils/douyin_api/`（自 douyin-downloader 单视频路径移植）。
