# B 站链接解析

自动识别群聊/好友中的 B 站链接并回复解析结果（视频、直播、短链、QQ 小程序分享）。

> **2.0 配置**：在 Web Admin → **群组** / **好友** 中按目标开关链接解析，可分别启用视频/直播解析。
>
> 完整文档：[链接解析](https://cyxc1124.github.io/cyxcbot/docs/plugins/link-parser)

## 触发方式

无需命令，发送含 BV 号、直播间链接、`b23.tv` 短链或 B 站 QQ 小程序分享的普通消息即可。

## 文件结构

```
plugins/bilibili_link_parser/
├── __init__.py       # 消息监听与解析调度
├── config.py         # 从 ConfigService 加载
├── message_text.py   # 消息文本提取
├── miniapp.py        # QQ 小程序分享解析
├── sender.py         # 回复消息构建
└── README.md
```
