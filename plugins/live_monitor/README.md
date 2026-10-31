# B 站直播监控

主动监控直播间开播/下播并推送通知，采用 WebSocket 弹幕 + API 轮询双重机制。

> **2.0 配置**：在 Web Admin → **B 站 → 直播订阅** 与 **B 站 → 订阅参数** 中管理房间映射、轮询间隔、WebSocket 开关等，不再使用 `LIVE_MONITOR_*` 环境变量。B 站账号在 **B 站 → 账号** 中配置。
>
> 完整文档：[直播监控](https://cyxc1124.github.io/cyxcbot/docs/plugins/live-monitor)

## 命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/直播状态 [房间号]` | `/查直播`、`/live` | 查询指定房间直播状态 |
| `/监控列表` | `/直播监控列表` | 列出当前群监控的房间 |

> 触发词可在 Web Admin → **系统 → 命令** 中自定义（含开关与恢复默认），保存后立即生效。

## 监控原理

1. **WebSocket 弹幕**（默认启用）：监听 `LIVE` / `PREPARING` 命令，秒级响应
2. **API 轮询**（备用）：WebSocket 启用时间隔约 5 分钟；禁用时作为主要方式

支持 OneBot 数字 QQ 目标与官方 QQ Bot 的官方群/C2C OpenID。开播/下播消息快照、失败目标与官方分段进度持久化到数据库，重启后继续未完成投递；首次订阅只记录基线，不补发当前场次。官方主动能力以平台权限和回执为准，`@全体` 使用文字提示。确定性平台拒绝结束对应目标，临时错误保留重试；未收到回执的网络超时无法保证严格去重。

## 文件结构

```
plugins/live_monitor/
├── __init__.py        # 插件入口、命令处理
├── config.py          # 从 ConfigService 加载配置
├── models.py          # 监控状态模型
├── live_monitor.py    # 监控核心逻辑
├── danmaku_client.py  # WebSocket 弹幕客户端
├── card_generator.py  # 开播/下播卡片
├── sender.py          # 通知发送
└── README.md
```

B 站直播 API 见 `utils/bilibili_api/`。
