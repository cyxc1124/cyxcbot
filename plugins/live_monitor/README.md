# B站直播监控插件

主动监控B站直播间开播/关播状态并发送通知，无需依赖 blrec 等外部工具。

## 功能特点

- 🔄 **主动监控**：通过定时轮询B站API检测直播状态，无需外部依赖
- 📢 **自动通知**：检测到开播/关播时自动发送群消息通知
- 🏠 **多房间支持**：支持同时监控多个直播间
- 👥 **多群组支持**：每个房间可配置多个目标群组
- 📌 **@全体成员**：开播时支持@全体成员（需要机器人管理员权限）
- ⚡ **实时查询**：支持手动查询直播间状态

## 监控原理

参考 [blrec](https://github.com/acgnhiki/blrec) 的实现，采用双重监控机制：

### 1. WebSocket 弹幕监听（主要方式，默认启用）

连接B站直播间的弹幕 WebSocket，实时监听状态命令：
- `LIVE` 命令 → 检测开播（秒级响应）
- `PREPARING` 命令 → 检测关播（秒级响应）

**优点**：实时性极高，几乎秒级响应
**缺点**：需要维护长连接，可能因网络问题断开

### 2. API 轮询（备用方式）

定时调用 `getInfoByRoom` 接口获取直播间信息：
- 当 WebSocket 启用时：作为备用，间隔较长（5分钟）
- 当 WebSocket 禁用时：作为主要方式，间隔可配置

**优点**：稳定可靠
**缺点**：有延迟，取决于轮询间隔

### 直播状态说明

| 状态 | 值 | 说明 |
|------|-----|------|
| PREPARING | 0 | 未开播/准备中 |
| LIVE | 1 | 直播中 |
| ROUND | 2 | 轮播中 |

## 配置说明

在 `.env` 文件中添加以下配置：

```env
# 房间号-群组映射配置（JSON格式）
# 格式：{"房间号": ["群组ID1", "群组ID2"], "房间号2": ["群组ID3"]}
LIVE_MONITOR_MAPPING={"12345678": ["123456789", "987654321"]}

# 直播状态检查间隔（秒，默认：60，最小：30）
# 如果启用了WebSocket，此间隔作为备用轮询间隔（会自动乘以5）
LIVE_MONITOR_INTERVAL=60

# 是否在通知中包含详细房间信息（默认：true）
LIVE_MONITOR_INCLUDE_INFO=true

# 是否启用 WebSocket 实时监控（默认：true，推荐）
# true: 使用 WebSocket 弹幕客户端实时监控（秒级响应）
# false: 仅使用 API 轮询
LIVE_MONITOR_USE_WEBSOCKET=true

# B站Cookie（可选，用于提高API和WebSocket稳定性）
BILIBILI_COOKIE=SESSDATA=xxxxx;DedeUserID=xxxxx;buvid3=xxxxx
```

### 配置项详解

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `LIVE_MONITOR_MAPPING` | JSON | `{}` | 房间号到群组的映射 |
| `LIVE_MONITOR_INTERVAL` | int | 60 | 检查间隔（秒），最小30秒 |
| `LIVE_MONITOR_INCLUDE_INFO` | bool | true | 是否包含详细信息 |
| `LIVE_MONITOR_USE_WEBSOCKET` | bool | true | 是否启用 WebSocket 实时监控 |
| `BILIBILI_COOKIE` | string | null | B站Cookie（可选） |

## 命令说明

| 命令 | 别名 | 说明 |
|------|------|------|
| `/直播状态 [房间号]` | `/查直播`, `/live` | 查询指定房间的直播状态 |
| `/监控列表` | `/直播监控列表` | 列出当前群组监控的房间 |

### 使用示例

```
用户: /直播状态 12345678
机器人: 🔴 主播名称
       状态：直播中
       房间号：12345678
       标题：今天来玩游戏！
       分区：游戏 - 单机游戏
       人气：12345
       直播间：https://live.bilibili.com/12345678

用户: /监控列表
机器人: 📺 当前群组监控的直播间 (2 个):
       🔴 主播A (12345678)
       ⚫ 主播B (87654321)
```

## 通知消息格式

### 开播通知

```
🎉 主播名称 开播啦！
直播间标题：今天来玩游戏！
房间号：12345678
开播时间：2024-01-01 20:00:00
分区：游戏 - 单机游戏
点我直达：https://live.bilibili.com/12345678
@全体成员
```

### 关播通知

```
【下播提醒】
主播名称下播啦！
直播时长：2小时30分钟15秒
```

## 与 stream_notify 的区别

| 特性 | live_monitor（本插件） | stream_notify |
|------|------------------------|---------------|
| 工作方式 | WebSocket + API轮询 | 被动接收webhook |
| 外部依赖 | 无 | 需要 blrec |
| 实时性 | 秒级（WebSocket）| 实时 |
| 资源消耗 | 需维护WebSocket连接 | 极低 |
| 适用场景 | 无法部署blrec时 | 有blrec环境时 |

**建议**：
- 如果已经部署了 blrec，建议使用 `stream_notify` 插件接收 webhook
- 如果无法部署 blrec 或需要独立的监控能力，使用本插件
- 本插件的 WebSocket 监控与 blrec 原理相同，实时性相当

## 注意事项

1. **API限制**：请求过于频繁可能被B站限制，建议检查间隔不低于30秒
2. **Cookie配置**：配置Cookie可以提高API稳定性，但需要定期更新
3. **权限要求**：@全体成员需要机器人具有管理员权限
4. **首次启动**：首次启动会初始化各房间状态，不会发送通知

## 文件结构

```
plugins/live_monitor/
├── __init__.py        # 插件入口，命令处理
├── config.py          # 配置管理
├── models.py          # 数据模型（LiveStatus, RoomInfo等）
├── live_api.py        # B站直播API调用
├── danmaku_client.py  # WebSocket弹幕客户端（实时监控）
├── live_monitor.py    # 监控核心逻辑
└── README.md          # 说明文档

# 依赖的公共模块
utils/bilibili_api/
├── wbi.py             # B站WBI签名模块（API鉴权，公共）
└── ...
```

## 更新日志

### v1.0.0
- 初始版本
- 支持主动监控直播状态
- 支持开播/关播通知
- 支持多房间多群组配置
