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

#### DYNAMIC_RSSHUB_BASE_URL
RSSHub服务的基础URL，可选配置，默认使用官方RSSHub
```bash
DYNAMIC_RSSHUB_BASE_URL=https://rsshub.app
```
如果官方RSSHub服务不稳定，可以配置自己的RSSHub实例或其他可用的RSSHub服务

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
   - 支持配置自定义RSSHub实例，提高服务稳定性
   - 默认使用官方RSSHub服务
2. **数据解析**：解析RSS feed中的动态ID、内容、发布时间等信息
3. **状态管理**：记录每个UP主的最后动态ID，避免重复推送
4. **消息推送**：发现新动态时推送到配置的群组

## RSSHub配置说明

插件使用RSSHub服务获取B站动态数据，为应对官方API不稳定的情况，提供了灵活的RSSHub配置选项：

### 为什么需要RSSHub配置

- **服务稳定性**：官方RSSHub可能存在访问限制或服务不稳定
- **网络环境**：某些地区可能无法正常访问官方RSSHub
- **私有部署**：企业或个人可以部署自己的RSSHub实例

### 配置选项

#### 使用官方RSSHub（默认）
无需额外配置，直接使用：
```bash
DYNAMIC_RSSHUB_BASE_URL=https://rsshub.app
```

#### 使用自建RSSHub实例
```bash
DYNAMIC_RSSHUB_BASE_URL=http://your-rsshub-instance.com
```

#### 使用其他RSSHub服务
```bash
DYNAMIC_RSSHUB_BASE_URL=https://rsshub.example.com
```

### RSSHub部署建议

如果需要自建RSSHub实例，推荐使用Docker部署：

```bash
docker run -d --name rsshub -p 1200:1200 diygod/rsshub
```

然后配置：
```bash
DYNAMIC_RSSHUB_BASE_URL=http://localhost:1200
```

## 注意事项

- 请确保机器人有相应群组的发送权限
- 监控间隔不建议设置过短，以避免对RSSHub造成过大压力
- 建议间隔时间在30秒到1小时之间
- RSSHub服务需要网络可访问
- 如果使用自建RSSHub，请确保B站相关路由已启用