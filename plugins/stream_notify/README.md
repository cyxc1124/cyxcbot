# B站直播通知插件

一个专用于B站直播通知的NoneBot2插件，通过blrec webhook接收直播事件并发送通知到QQ群。

## 功能特性

- 🎉 **开播通知** - 主播开播时自动@全体成员
- 😴 **下播提醒** - 显示直播时长和结束提醒
- 🔗 **直播链接** - 直接跳转到B站直播间
- 🕐 **开播时间** - 显示具体的开播时间
- ⏱️ **直播时长** - 下播时显示本次直播时长
- 🔐 **安全验证** - API密钥验证确保安全性
- 📱 **多群通知** - 支持同时向多个QQ群发送通知
- 📊 **详细信息** - 包含直播间标题、房间号、分区等信息

## 消息格式

### 开播消息
```
🎉 {主播名} 开播啦！
📺 直播间标题：{标题}
🔢 房间号：{房间号}
🕐 开播时间：{开播时间}
🔗 点我直达：https://live.bilibili.com/{房间号}
@全体成员
```

### 下播消息
```
【下播提醒】
{主播名}下播啦！
直播时长：{时长}
```

## API接口

### 接口地址
```
POST http://your_bot_host:8080/api/bilibili/live
```

### 请求格式
```json
{
    "secret": "your_secret_key",
    "type": "LiveBeganEvent",  // "LiveBeganEvent" 表示开播，"LiveEndedEvent" 表示下播
    "data": {
        "user_info": {
            "name": "主播名称",
            "uid": 123456789
        },
        "room_info": {
            "room_id": "21919321",
            "title": "直播标题",
            "area_name": "虚拟主播",
            "live_start_time": 1644753625,  // 开播时间戳（开播事件）
            "online": 9000  // 直播时长（秒，下播事件）
        }
    }
}
```

### 响应格式
```json
{
    "success": true,
    "message": "B站直播事件处理成功"
}
```

## 配置项

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 通知群组 | `STREAM_NOTIFY_NOTIFY_GROUPS` | `["364477847"]` | 需要发送通知的群组ID列表 |
| API密钥 | `STREAM_NOTIFY_API_SECRET` | `"your_secret_key"` | 用于验证blrec webhook请求 |
| 房间信息 | `STREAM_NOTIFY_INCLUDE_ROOM_INFO` | `true` | 是否包含房间信息（标题、链接等） |
| 主播名称 | `STREAM_NOTIFY_STREAMER_NAME` | `"主播"` | 主播名称（当API请求中未提供时使用） |

## 使用示例

### 开播事件
```bash
curl -X POST http://127.0.0.1:8080/api/bilibili/live \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "your_secret_key",
    "type": "LiveBeganEvent",
    "data": {
        "user_info": {
            "name": "HiiroVTuber",
            "uid": 508963009
        },
        "room_info": {
            "room_id": "21919321",
            "title": "周末三国",
            "area_name": "虚拟主播",
            "live_start_time": 1644753625
        }
    }
  }'
```

### 下播事件
```bash
curl -X POST http://127.0.0.1:8080/api/bilibili/live \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "your_secret_key",
    "type": "LiveEndedEvent",
    "data": {
        "user_info": {
            "name": "HiiroVTuber",
            "uid": 508963009
        },
        "room_info": {
            "room_id": "21919321",
            "title": "周末三国",
            "online": 9000
        }
    }
  }'
```

## 集成说明

### 与blrec集成

在blrec的webhook配置中设置：
- URL: `http://your_bot_ip:8080/api/bilibili/live`
- Secret: 与插件配置中的API密钥一致

### 错误处理

- **401错误**: API密钥验证失败
- **400错误**: 不支持的事件类型
- **500错误**: 服务器内部错误

## 注意事项

1. 确保机器人已加入目标QQ群并有发送消息权限
2. 需要配置OneBot适配器连接（如go-cqhttp）
3. 请设置安全的API密钥
4. 确保blrec能够访问到机器人的API接口
5. 插件会自动处理时间戳转换和时长格式化

## 测试

项目提供了测试脚本来验证插件功能：

```bash
# 测试API接口
python test_api.py

# 测试环境配置
python test_env.py
``` 