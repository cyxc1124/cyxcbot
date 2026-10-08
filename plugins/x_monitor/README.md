# X (Twitter) 监控

监控 X 博主新推文，向配置的群/好友自动推送。v1 不含置顶、截图与群查询命令。

> 配置走 Web Admin + 数据库：Bearer Token（加密）、代理（http/https/socks5）、博主 username 与推送映射。

## 文件结构

```
plugins/x_monitor/
├── __init__.py        # 插件入口、生命周期（无群命令）
├── config.py          # 从 ConfigService 加载配置
├── x_monitor.py       # 轮询监控核心
├── check_logic.py     # 新推文收集 / 首次基准
├── state_store.py     # 游标持久化
├── poll_scheduler.py  # APScheduler 任务
├── sender.py          # 消息构建与发送
└── README.md
```

X API 封装见 `utils/x_api/`。

## 官方 QQ Bot

- 数字 QQ 号走 OneBot，官方 openid 走 QQ 适配器；群与 C2C 均可作为监控目标。
- 官方消息的每个文字/图片/视频分段成功后保存进度；OneBot 保存批次进度。已成功的目标不随其他目标失败重复发送。
- 平台权限/内容等终止拒绝不会卡住游标；频控、断连与未知错误继续重试。重试需重新获取推文及下载媒体，暂存文件每轮清理。
- 群 `@全体` 在官方侧使用文字提示；修改前缀策略会使新版本的未完成计划失效，防止按旧下标跳过内容。旧 OneBot 进度保留兼容。
- [腾讯文档](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/overview.html)说明当前允许主动发送；用户可关闭允许主动发送开关，发送仍受频控及应用权限约束。本模块适配官方群/C2C 主动推送，请按实际回执判断送达情况。
