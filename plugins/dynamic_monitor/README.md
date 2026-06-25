# UP 主动态监控

监控 B 站 UP 主动态更新，向配置的群/好友推送通知；支持主动查询与动态图片提取。

> **2.0 配置**：在 Web Admin → **动态监控** 与 **设置 → 监控参数** 中管理 UP 主映射、间隔、截图开关等，不再使用 `DYNAMIC_MONITOR_*` 环境变量。
>
> 完整文档：[动态监控](https://cyxc1124.github.io/cyxcbot/docs/plugins/dynamic-monitor)

## 命令

在已配置 UP 主映射的群中：

| 命令 | 说明 |
|------|------|
| `最新动态` | 主动查询 UP 主最新动态 |
| `置顶动态` | 主动查询 UP 主置顶动态 |
| `#提取 <动态ID>` / `#获取 <动态ID>` | 按动态 ID 拉取图片（群聊/私聊） |

## 文件结构

```
plugins/dynamic_monitor/
├── __init__.py          # 插件入口、生命周期、查询命令
├── config.py            # 从 ConfigService 加载配置
├── dynamic_monitor.py   # 轮询监控核心逻辑
├── dynamic_extract.py   # 动态图片提取
├── sender.py            # 消息构建与发送
└── README.md
```

B 站 API 封装见 `utils/bilibili_api/`；截图见 `utils/screenshot/`。
