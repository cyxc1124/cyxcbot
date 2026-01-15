# UP主动态监控插件

监控B站UP主动态更新，并在指定群组发送通知。

## 功能特性

- 自动监控指定UP主的动态更新
- 支持多UP主多群组配置
- 可配置监控间隔时间
- 支持动态详情展示
- 直接调用B站Web API获取动态数据

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

#### DYNAMIC_ENABLE_SCREENSHOT
是否启用动态截图功能，默认true
```bash
DYNAMIC_ENABLE_SCREENSHOT=true
```
启用后会在推送消息中包含动态的网页截图，提供更丰富的视觉体验


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

1. **数据获取**：直接调用B站Web API获取UP主动态数据
   - 使用`https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space`接口
   - 支持获取用户空间的最新动态列表
- 只解析必要的基本信息（ID、类型、作者、时间）
- 智能处理置顶动态：只在置顶内容更换时推送，避免重复通知
- 支持识别多种动态类型和转发内容详情
- 过滤直播动态（DYNAMIC_TYPE_LIVE_RCMD 和 DYNAMIC_TYPE_LIVE）：直播推送由其他插件负责
- 首次启动保护：避免推送历史动态，只记录最新动态作为基准点
- 容器化部署：状态存储在内存中，重启后重新初始化，避免重复推送
2. **数据解析**：解析RSS feed中的动态ID、内容、发布时间等信息
   - 用户名提取：严格使用RSS标准的`<author>`字段，确保准确性
3. **内容处理**：清理和格式化动态内容，移除HTML实体和多余格式
4. **动态截图**：可选的动态网页截图功能，提供丰富的视觉体验
   - 使用Playwright进行网页截图
   - 支持移动端视图优化
5. **状态管理**：记录每个UP主的最后动态ID，避免重复推送
6. **消息推送**：发现新动态时以格式化的消息推送到配置的群组

## 消息格式

推送的消息格式如下：

```
小草Miho 发布了新投稿视频

[动态网页截图图片]

https://t.bilibili.com/1071700825512869927
```

转发动态示例：

```
小草Miho 转发了小明同学的视频

[动态网页截图图片]

https://t.bilibili.com/动态ID
```

**消息特点**：
- 简洁明了的信息展示
- 可选的动态截图展示
- 直接的动态链接跳转
- 支持多种动态类型识别（视频、转发、图文等）

## B站API说明

插件直接调用B站官方Web API获取动态数据，具有以下优势：

### API优势

- **无需第三方服务**：直接调用B站API，不依赖RSSHub等中间服务
- **数据实时性**：获取最新的动态数据，无缓存延迟
- **功能完整性**：支持获取完整的动态信息和元数据
- **稳定性高**：不受第三方服务波动影响

### API接口

插件使用以下B站API接口：
- **动态获取**: `https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space`
- **参数说明**:
  - `host_mid`: 用户UID
  - `timezone_offset`: 时区偏移（东八区为-480）
  - `platform`: 平台类型（web）
  - `pn`: 页码
  - `ps`: 每页数量

### 支持的动态类型

插件支持识别以下B站动态类型：

| B站类型 | 内部编号 | 说明 |
|---------|----------|------|
| `DYNAMIC_TYPE_WORD` | 4 | 纯文字动态 |
| `DYNAMIC_TYPE_DRAW` | 2 | 图文动态 |
| `DYNAMIC_TYPE_FORWARD` | 1 | 转发动态 |
| `DYNAMIC_TYPE_AV` | 8 | 投稿视频动态 |
| `DYNAMIC_TYPE_ARTICLE` | 64 | 投稿专栏动态 |
| `DYNAMIC_TYPE_MUSIC` | 256 | 投稿音频动态 |
| `DYNAMIC_TYPE_LIVE` | 16 | 直播动态 |
| `DYNAMIC_TYPE_LIVE_RCMD` | 16 | 直播推荐动态 |

### 支持的作者类型

插件支持识别以下作者类型：

| 作者类型 | 说明 |
|----------|------|
| `AUTHOR_TYPE_NORMAL` | 普通用户 |
| `AUTHOR_TYPE_OFFICIAL` | 官方账号 |
| `AUTHOR_TYPE_BIZ` | 商业账号 |
| `AUTHOR_TYPE_BIG_VIP` | 大会员账号 |

## 动态截图功能

插件提供了可选的动态网页截图功能，可以在推送消息中包含动态的视觉内容：

### 功能特点

- **网页截图**：使用Playwright获取动态页面的截图
- **移动端优化**：使用移动端视图尺寸，适配移动设备
- **智能裁剪**：自动识别动态卡片区域，避免截取无关内容
- **容错处理**：截图失败时自动降级为文字消息

### 配置选项

```bash
# 启用截图功能（默认）
DYNAMIC_ENABLE_SCREENSHOT=true

# 禁用截图功能
DYNAMIC_ENABLE_SCREENSHOT=false
```

### 依赖要求

启用截图功能需要安装Playwright：

```bash
pip install playwright==1.40.0
playwright install chromium
```

### 注意事项

- 截图功能需要额外的系统资源
- 首次运行可能需要下载浏览器内核
- 网络不稳定时可能影响截图质量
- 可以随时通过配置开关启用/禁用

## 注意事项

- 请确保机器人有相应群组的发送权限
- 监控间隔不建议设置过短，以避免对B站API造成过大压力
- 建议间隔时间在30秒到5分钟之间
- 需要网络可访问B站API服务
- 插件会自动处理API响应和错误情况