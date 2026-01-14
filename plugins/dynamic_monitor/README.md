# UP主动态监控插件

监控B站UP主动态更新，并在指定群组发送通知。

## 功能特性

- 自动监控指定UP主的动态更新
- 支持多UP主多群组配置
- 可配置监控间隔时间
- 支持动态详情展示
- 使用RSSHub获取数据，无需B站API

## 配置说明

### 环境变量配置

#### DYNAMIC_MONITOR_MAPPING
配置UP主UID与群组ID的映射关系，JSON格式：
```json
{
  "12345678": ["group_id_1", "group_id_2"],
  "87654321": ["group_id_3"]
}
```

#### DYNAMIC_MONITOR_INTERVAL
监控间隔时间（秒），默认300秒（5分钟）
```bash
DYNAMIC_MONITOR_INTERVAL=300
```

#### DYNAMIC_INCLUDE_DETAILS
是否包含动态详情，默认true
```bash
DYNAMIC_INCLUDE_DETAILS=true
```

## 使用方法

1. 配置环境变量
2. 重启机器人
3. 插件将自动开始监控并推送新动态

## 文件结构

```
plugins/dynamic_monitor/
├── __init__.py          # 插件入口和生命周期管理
├── config.py           # 配置类（环境变量支持）
├── models.py           # 动态数据模型定义
├── fetcher.py          # RSS数据获取和解析
├── sender.py           # 消息构建和发送
├── dynamic_monitor.py  # 核心监控逻辑协调
└── README.md          # 使用说明文档
```

## 日志系统

插件使用NoneBot的标准日志系统，提供以下日志级别：

- **DEBUG**: 详细的调试信息（如检查动态状态）
- **INFO**: 重要事件（如发现新动态、启动/停止监控）
- **WARNING**: 警告信息（如获取动态失败）
- **ERROR**: 错误信息（如网络异常、发送失败）

日志输出到NoneBot的统一日志系统，支持配置输出格式、级别和文件输出。

## 工作原理

1. **数据获取**：通过RSSHub的B站动态RSS源获取UP主动态数据
2. **数据解析**：解析RSS feed中的动态ID、内容、发布时间等信息
3. **状态管理**：记录每个UP主的最后动态ID，避免重复推送
4. **消息推送**：发现新动态时推送到配置的群组

## 注意事项

- 请确保机器人有相应群组的发送权限
- 监控间隔不建议设置过短，以避免对RSSHub造成过大压力
- 建议间隔时间在30秒到1小时之间
- RSSHub服务需要网络可访问