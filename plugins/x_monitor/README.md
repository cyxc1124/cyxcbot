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
