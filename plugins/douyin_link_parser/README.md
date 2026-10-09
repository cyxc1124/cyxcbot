# 抖音链接解析

自动识别群聊 / 私聊中的抖音分享链接（含 `v.douyin.com` 短链），下载无水印视频 / 图集 / Live 图并以 QQ 消息回传。Live 图按视频段发送。

## 行为

- 监听 `on_message(priority=4, block=False)`（与 B 站链接解析同级，互不 `block`）
- 策略默认关闭；仅当群 / 好友在 Web Admin「抖音链接」中开启后生效
- Cookie 独立于 B 站（设置 → 抖音账号）；**非硬性必填**，对齐 douyin-downloader：缺省仅 warning，仍尝试游客态；建议配置 `ttwid` / `odin_tt` / `passport_csrf_token`（`msToken` 可缺省自动生成）
- 支持 `aweme_type` 视频（0/4）与图集（2/68）；Live Photo 取 `images[].video.play_addr` 以视频发送
- 文案模板键：`link_template_douyin`（占位符：`{video}` `{title}` `{author}` `{url}` `{aweme_id}`；`{video}` 会展开为全部图片/视频段）
- 含视频段时拆开发送（先媒体后文案）：QQ 同条混排 video 时常吞掉文字
- 图集图片过多时按批发送（每条最多 10 张），避免 QQ NT `sendMsg result=34`
- 媒体写入「设置 → 机器人」的共享媒体目录并以 `file://` 发送（与 B 站一致；上限 1024MB）

## 官方 QQ Bot

- 支持官方群与 C2C 的原生消息事件，回复使用原消息 ID 和 SDK 递增序号；文字、图片和视频通过现有 QQ 适配层回传，OneBot 行为保持原样。
- 按[当前官方消息规则](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/overview.html)安排预算：群聊每条消息最多五次被动回复、单聊四次。为文案保留一次回复，超预算的多张静态图片合成一张带序号的预览，混合图集优先保留预览；视频和 Live 按原顺序回传预算内部分，剩余数量会明确提示在原作品查看。只剩一次回复时仅发送遗漏说明，不生成预览。
- 合成预览仅使用已下载的本地图片；过大像素图片不在本地解码。合成失败时按剩余预算回传原媒体，并提示限制。
- 生成预览、原始媒体都在发送完成或失败后清理；取消渲染时等待后台线程完成清理。正常平台拒绝记业务警告，不重复打印异常栈。
- 当前官方接口允许主动发送，但本插件是用户分享链接后的被动回复。主动推送与回复权限、频控以实际应用及回执为准。

## 配置入口

| 位置 | 说明 |
|------|------|
| 群管理 → 抖音链接 | 按群开关 |
| 好友管理 → 抖音链接 | 按好友开关 |
| 设置 → 抖音账号 | 扫码登录（Playwright，对齐 douyin_parse）或粘贴 Cookie |
| 设置 → 机器人 → 链接解析共享媒体目录 | 与协议端同路径可见；空则平台默认 |

## 实现

下载链路见 `utils/douyin_api/`（视频路径自 douyin-downloader；图集/Live 判定对齐 douyin_parse）。
